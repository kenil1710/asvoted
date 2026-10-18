/**
 * The patrol's durable state: one JSON document, committed by the GitHub
 * Action to the `patrol-state` branch after every live run
 * (.github/workflows/patrol.yml) and handed back to the next run.
 *
 * Why a branch: the patrol runs in a stateless Vercel function, so the state
 * has to live somewhere else. A JSON file on a dedicated branch needs no new
 * service or credential (the Action's GITHUB_TOKEN), keeps every checkpoint
 * move as a commit anyone can audit, is readable by the site for the
 * "Unmatched executions" page, and has exactly one writer: the workflow's
 * concurrency group runs one patrol at a time.
 *
 *   checkpoints  "chain|safe" -> the last block fully scanned for that Safe
 *   processed    "chain|safe|safeTxHash" -> what became of that execution
 *   retry        executions that failed or were deferred, with attempt counts
 *   unmatched    executions no passed proposal could be matched to
 *   heartbeats   "chain|safe" -> the block last sent to the registry as
 *                coverage (record_coverage), so an unchanged one is not resent
 *   cursors      where a bounded run stopped in the registry's paginated
 *                lists (DAOs, open checks); the next run continues there
 */

export const STATE_VERSION = 1;

export interface Checkpoint {
  block: number;          // last block fully scanned (every event in it processed or queued)
  origin: number;         // the block the first scan of this Safe started from
  updated: string;
}

export interface Processed {
  status: "filed" | "on_registry" | "unmatched";
  check_id: number;
  tx: string;
  block: number;
  at: string;
}

export interface RetryEntry {
  key: string;
  dao_id: number;
  space: string;
  chain: string;
  safe: string;
  tx: string;
  safe_tx_hash: string;
  block: number;
  attempts: number;       // failed attempts so far (a deferral for lack of budget is not one)
  next_at: number;        // unix seconds; not retried before
  last_error: string;
  first_seen: string;
}

export interface Unmatched {
  key: string;
  dao_id: number;
  space: string;
  chain: string;
  safe: string;
  tx: string;
  safe_tx_hash: string;
  block: number;
  reason: string;
  at: string;
}

export interface Cursors {
  daos: number;           // index of the next DAO to scan (round robin over every page of get_daos)
  open_checks: number;    // get_open_checks offset to continue from
}

export interface PatrolState {
  version: number;
  updated: string;
  cursors: Cursors;
  heartbeats: Record<string, number>;
  checkpoints: Record<string, Checkpoint>;
  processed: Record<string, Processed>;
  retry: RetryEntry[];
  unmatched: Unmatched[];
}

export const emptyState = (): PatrolState => ({
  version: STATE_VERSION, updated: "", cursors: { daos: 0, open_checks: 0 }, heartbeats: {}, checkpoints: {}, processed: {}, retry: [], unmatched: [],
});

/** A state document from untrusted JSON: anything missing or malformed starts empty. */
export function loadState(raw: unknown): PatrolState {
  const s = emptyState();
  if (!raw || typeof raw !== "object") return s;
  const r = raw as Record<string, unknown>;
  const obj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, never>) : {});
  const arr = (v: unknown) => (Array.isArray(v) ? (v as never[]) : []);
  s.updated = typeof r.updated === "string" ? r.updated : "";
  const cur = obj(r.cursors) as Partial<Cursors>;
  const nat = (v: unknown) => (Number.isInteger(v) && (v as number) >= 0 ? (v as number) : 0);
  s.cursors = { daos: nat(cur.daos), open_checks: nat(cur.open_checks) };
  for (const [k, v] of Object.entries(obj(r.checkpoints))) {
    const c = v as Checkpoint;
    if (Number.isInteger(c?.block) && c.block >= 0) s.checkpoints[k] = { block: c.block, origin: Number(c.origin ?? c.block), updated: String(c.updated ?? "") };
  }
  for (const [k, v] of Object.entries(obj(r.heartbeats))) if (Number.isInteger(v) && (v as number) >= 0) s.heartbeats[k] = v as number;
  s.processed = obj(r.processed);
  s.retry = arr(r.retry).filter((e: RetryEntry) => typeof e?.key === "string");
  s.unmatched = arr(r.unmatched).filter((e: Unmatched) => typeof e?.key === "string");
  return s;
}

export const safeKey = (chain: string, safe: string) => `${chain.toLowerCase()}|${safe.toLowerCase()}`;
/** The idempotency key of one execution. */
export const execKey = (chain: string, safe: string, safeTxHash: string) => `${safeKey(chain, safe)}|${safeTxHash.toLowerCase()}`;

const RETRY_BASE_S = 900;
const RETRY_MAX_S = 6 * 3600;
export const backoff = (attempts: number) => Math.min(RETRY_BASE_S * 2 ** Math.max(attempts - 1, 0), RETRY_MAX_S);

/** Adds or updates a retry entry. `failed` counts an attempt; a deferral does not. */
export function enqueue(s: PatrolState, e: Omit<RetryEntry, "attempts" | "next_at" | "first_seen" | "last_error">, now: number, error: string, failed: boolean) {
  const at = s.retry.find((x) => x.key === e.key);
  const attempts = (at?.attempts ?? 0) + (failed ? 1 : 0);
  const next = { ...e, attempts, next_at: failed ? now + backoff(attempts) : now, last_error: error.slice(0, 200),
    first_seen: at?.first_seen ?? new Date(now * 1000).toISOString() };
  if (at) Object.assign(at, next);
  else s.retry.push(next);
}

export const dequeue = (s: PatrolState, key: string) => { s.retry = s.retry.filter((x) => x.key !== key); };
