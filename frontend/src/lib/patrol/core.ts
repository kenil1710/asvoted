/**
 * The patrol's logic, with every outside effect injected (Deps), so the same
 * code runs live (../patrol.ts) and against mocked chains and registries
 * (frontend/test).
 *
 * One run, bounded by limits.maxWrites transactions and limits.timeBudgetMs:
 *   1. close its own filings: rule what is judged, judge what is not, finalize
 *      what is past its contest window, expire what is past its active
 *      deadline (round 2: the DAO's resp_deadline, not appeal_deadline). Every
 *      page of get_open_checks (each call scans at most the registry's
 *      SCAN_CAP records and returns at most 50), from state.cursors;
 *   2. retry the executions queued by earlier runs whose backoff has passed;
 *   3. for every DAO on the registry (every page of get_daos, round robin
 *      from state.cursors.daos when a run runs out of time), scan its Safe's ExecutionSuccess logs
 *      from the Safe's checkpoint + 1 up to the chain's finalized block, at
 *      most limits.maxSpan blocks per run; every event is either processed
 *      (filed, already on the registry, or recorded as unmatched) or queued
 *      for retry, and only then does the checkpoint move to the end of the
 *      span. A log range that cannot be read stops the scan there, and the
 *      checkpoint stays at the last range read in full;
 *   4. record a coverage heartbeat on the registry (record_coverage): per
 *      DAO, the last block through which every execution was handled. One
 *      write is held back for it.
 *
 * Idempotency: an execution is keyed by (chain, Safe, safeTxHash). A key in
 * state.processed is never handled again, and before any filing the registry
 * is asked for an existing check of that transaction.
 */
import type { CalldataEncodable } from "genlayer-js/types";
import { type PatrolState, dequeue, enqueue, execKey, safeKey } from "./state";

export const STAKE = 10n ** 17n;

export interface Dao { dao_id: number; space: string; chain: string; safe: string }
export interface Log { tx: string; block: number; safeTxHash: string }
export interface WriteResult { ok: boolean; hash: string | null; note: string; dry?: boolean }
export type Match = { cid: string; nonce: number; why: string } | { error: string; unmatched: boolean };

export interface Deps {
  now(): number;
  elapsedMs(): number;
  patrol: string;
  dry: boolean;
  addr: { registry: string; execReader: string; voteReader: string; judge: string };
  view<T>(address: string, fn: string, args?: CalldataEncodable[]): Promise<T>;
  write(address: string, fn: string, args: CalldataEncodable[], value?: bigint): Promise<WriteResult>;
  finalized(chain: string): Promise<{ number: number; timestamp: number }>;
  blockTime(chain: string, block: number): Promise<number>;
  logs(chain: string, safe: string, from: number, to: number): Promise<Log[]>;
  match(d: Dao, log: Log): Promise<Match>;
  supported(chain: string): boolean;
}

export interface Limits {
  maxWrites: number;
  timeBudgetMs: number;
  /** most blocks of one Safe scanned in one run */
  maxSpan: Record<string, number>;
  /** blocks per eth_getLogs call */
  logChunk: number;
  /** where a Safe with no checkpoint starts, in blocks before the finalized head */
  initialBackfill: Record<string, number>;
}

// ~24 h of blocks per run (arbitrum ~7.5 h, at 0.25 s blocks); a first scan starts ~7 days back
export const LIMITS: Limits = {
  maxWrites: 5,
  timeBudgetMs: 240_000,
  maxSpan: { ethereum: 7_200, optimism: 43_200, base: 43_200, polygon: 43_200, arbitrum: 108_000 },
  logChunk: 9_000,
  initialBackfill: { ethereum: 50_400, optimism: 302_400, base: 302_400, polygon: 302_400, arbitrum: 2_419_200 },
};

export interface WriteLog { fn: string; args: string; ok: boolean; hash: string | null; note: string }
export interface ScanLog { dao: string; chain: string; safe: string; from: number; to: number; checkpoint: number; events: number; complete: boolean }
export interface RunReport {
  started: string;
  dry_run: boolean;
  patrol: string;
  registry: string;
  writes: WriteLog[];
  daos_watched: number;
  open_pages: number;
  open_seen: number;
  executions_seen: number;
  already_checked: number;
  filed: number;
  queued: number;
  retried: number;
  unmatched: number;
  heartbeats: number;
  scans: ScanLog[];
  matched: { tx: string; dao: string; cid: string; why: string }[];
  closed: string[];
  notes: string[];
  seconds: number;
}

/**
 * The deadline that governs an open check now. Round 2 (the DAO's response to
 * a DEVIATES an appeal produced) runs to resp_deadline, which is later than
 * the round-1 appeal_deadline: expiring on appeal_deadline would be refused,
 * and judging must continue until resp_deadline.
 */
export function activeDeadline(c: { status: string; round: number; judge_deadline: number; contest_deadline: number; appeal_deadline: number; resp_deadline?: number; active_deadline?: number }): number {
  if (typeof c.active_deadline === "number" && c.active_deadline > 0) return c.active_deadline;
  if (c.status === "PROVISIONAL") return c.judge_deadline;
  if (c.status === "CONTESTABLE") return c.contest_deadline;
  if (c.status === "APPEALED") return c.round === 2 ? Number(c.resp_deadline ?? 0) : c.appeal_deadline;
  return 0;
}

const short = (e: unknown) => String((e as Error)?.message ?? e).slice(0, 120);

export async function runCore(deps: Deps, state: PatrolState, limits: Limits = LIMITS): Promise<RunReport> {
  const { addr } = deps;
  const rep: RunReport = {
    started: new Date(deps.now() * 1000).toISOString(), dry_run: deps.dry, patrol: deps.patrol, registry: addr.registry,
    writes: [], daos_watched: 0, open_pages: 0, open_seen: 0, executions_seen: 0, already_checked: 0, filed: 0, queued: 0, retried: 0, unmatched: 0, heartbeats: 0,
    scans: [], matched: [], closed: [], notes: [], seconds: 0,
  };
  const iso = () => new Date(deps.now() * 1000).toISOString();
  const timeLeft = () => deps.elapsedMs() < limits.timeBudgetMs;
  // one write is held back for the coverage heartbeat at the end of the run
  const budgetLeft = () => rep.writes.length < limits.maxWrites - 1 && timeLeft();

  async function write(address: string, fn: string, args: CalldataEncodable[], value = 0n): Promise<WriteResult> {
    const r = await deps.write(address, fn, args, value);
    rep.writes.push({ fn, args: JSON.stringify(args).slice(0, 160), ok: r.ok, hash: r.hash, note: r.note });
    return r;
  }

  // 1. close our own filings, every page of open checks, continuing where the last run stopped
  const PAGE = 50;
  type Open = { check_id: number; status: string; round: number; filer: string; judge_deadline: number; contest_deadline: number;
    appeal_deadline: number; resp_deadline?: number; active_deadline?: number };
  async function close(c: Open): Promise<void> {
    const now = deps.now();
    const deadline = activeDeadline(c);
    if (c.status === "CONTESTABLE") {
      if (now > deadline) { rep.closed.push(`finalize #${c.check_id}`); await write(addr.registry, "finalize", [c.check_id]); }
      return;
    }
    if (c.status !== "PROVISIONAL" && c.status !== "APPEALED") return;
    if (now > deadline) { rep.closed.push(`expire #${c.check_id}`); await write(addr.registry, "expire", [c.check_id]); return; }
    const j = await deps.view<{ found: boolean }>(addr.judge, "get_judgment", [addr.registry, c.check_id, c.round]);
    if (!j.found) { rep.closed.push(`judge #${c.check_id} round ${c.round}`); if (!(await write(addr.judge, "judge", [addr.registry, c.check_id])).ok) return; }
    if (budgetLeft()) { rep.closed.push(`rule #${c.check_id} round ${c.round}`); await write(addr.registry, "rule", [c.check_id]); }
  }
  try {
    const start = state.cursors.open_checks;
    let off = start;
    let wrapped = false;
    pages: for (;;) {
      if (!budgetLeft()) break;
      const page = await deps.view<{ next_offset: number; done: boolean; checks: Open[] }>(addr.registry, "get_open_checks", [off, PAGE]);
      rep.open_pages++;
      for (const c of page.checks) {
        if (wrapped && c.check_id > start) { state.cursors.open_checks = start; break pages; }
        if (!budgetLeft()) { state.cursors.open_checks = c.check_id - 1; break pages; }
        rep.open_seen++;
        if (!deps.patrol || c.filer !== deps.patrol) continue;
        await close(c);
      }
      off = page.done ? 0 : page.next_offset;
      state.cursors.open_checks = off;
      if (page.done) {
        if (wrapped || start === 0) { state.cursors.open_checks = start; break; }
        wrapped = true;
      } else if (wrapped && off >= start) { state.cursors.open_checks = start; break; }
    }
  } catch (e) { rep.notes.push("open checks unreadable: " + short(e)); }

  /**
   * One execution, start to finish or as far as the budget allows. Returns
   * "done" (filed, already on the registry, or recorded as unmatched) or
   * "queued" (in state.retry for a later run). Never throws.
   */
  async function handle(d: Dao, lg: Log): Promise<"done" | "queued"> {
    const key = execKey(d.chain, d.safe, lg.safeTxHash);
    const entry = { key, dao_id: d.dao_id, space: d.space, chain: d.chain, safe: d.safe.toLowerCase(), tx: lg.tx, safe_tx_hash: lg.safeTxHash.toLowerCase(), block: lg.block };
    const defer = (why: string) => { enqueue(state, entry, deps.now(), why, false); rep.queued++; return "queued" as const; };
    const fail = (why: string) => { enqueue(state, entry, deps.now(), why, true); rep.queued++; rep.notes.push(`${d.space} ${lg.tx.slice(0, 10)}: ${why}`); return "queued" as const; };
    const done = (status: "filed" | "on_registry" | "unmatched", check_id = 0) => {
      state.processed[key] = { status, check_id, tx: lg.tx, block: lg.block, at: iso() };
      dequeue(state, key);
      return "done" as const;
    };
    if (state.processed[key]) { rep.already_checked++; dequeue(state, key); return "done"; }
    try {
      const existing = Number(await deps.view<number>(addr.registry, "get_check_id_by_tx", [d.chain, d.safe, lg.tx]));
      if (existing) { rep.already_checked++; return done("on_registry", existing); }
      if (!budgetLeft()) return defer("budget used up; next run");
      const m = await deps.match(d, lg);
      if ("error" in m) {
        if (!m.unmatched) return fail(m.error);
        state.unmatched = state.unmatched.filter((u) => u.key !== key);
        state.unmatched.push({ ...entry, reason: m.error, at: iso() });
        rep.unmatched++;
        return done("unmatched");
      }
      rep.matched.push({ tx: lg.tx, dao: d.space, cid: m.cid, why: m.why });
      const now = deps.now();
      const sent = async (address: string, fn: string, args: CalldataEncodable[], value = 0n) => {
        const r = await write(address, fn, args, value);
        return r.ok ? "" : r.dry ? "dry run" : `${fn}: ${r.note}`;
      };
      let execId = Number(await deps.view<number>(addr.execReader, "get_execution_id", [d.chain, d.safe, lg.tx]));
      if (!execId) {
        const err = await sent(addr.execReader, "read_execution", [d.chain, d.safe, lg.tx, m.nonce]);
        if (err) return err === "dry run" ? defer(err) : fail(err);
        execId = Number(await deps.view<number>(addr.execReader, "get_execution_id", [d.chain, d.safe, lg.tx]));
        if (!execId) return fail("read_execution left no record");
      }
      if (!budgetLeft()) return defer("budget used up after read_execution; next run");
      let voteId = Number(await deps.view<number>(addr.voteReader, "get_proposal_id", [m.cid, d.chain, d.safe]));
      const v = voteId ? await deps.view<{ read_at: number }>(addr.voteReader, "get_proposal", [voteId]) : null;
      if (!v || now - v.read_at > 3000) {
        const err = await sent(addr.voteReader, "read_proposal", [m.cid, d.chain, d.safe]);
        if (err) return err === "dry run" ? defer(err) : fail(err);
        voteId = Number(await deps.view<number>(addr.voteReader, "get_proposal_id", [m.cid, d.chain, d.safe]));
        if (!voteId) return fail("read_proposal left no record");
      }
      if (!budgetLeft()) return defer("budget used up after read_proposal; next run");
      // ENS names as of the execution's L1 block, which a filing needs
      const pv = await deps.view<{ ens_names?: string[] }>(addr.voteReader, "get_proposal", [voteId]);
      const ev = await deps.view<{ l1_block: number }>(addr.execReader, "get_execution", [execId]);
      if (pv.ens_names?.length && ev.l1_block > 0 && !(await deps.view<{ found: boolean }>(addr.voteReader, "get_names_at", [voteId, ev.l1_block])).found) {
        const err = await sent(addr.voteReader, "read_names_at", [voteId, ev.l1_block]);
        if (err) return err === "dry run" ? defer(err) : fail(err);
        if (!budgetLeft()) return defer("budget used up after read_names_at; next run");
      }
      // the registry once more, right before the only write that costs a stake
      const again = Number(await deps.view<number>(addr.registry, "get_check_id_by_tx", [d.chain, d.safe, lg.tx]));
      if (again) { rep.already_checked++; return done("on_registry", again); }
      const err = await sent(addr.registry, "file_check", [d.dao_id, execId, voteId, `patrol: ${m.why}`.slice(0, 200)], STAKE);
      if (err) return err === "dry run" ? defer(err) : fail(err);
      const filed = Number(await deps.view<number>(addr.registry, "get_check_id_by_tx", [d.chain, d.safe, lg.tx]));
      if (!filed) return fail("file_check left no check on the registry");
      rep.filed++;
      return done("filed", filed);
    } catch (e) {
      return fail("error: " + short(e));
    }
  }

  // 2. the retry queue, oldest first, as far as the time budget goes
  const dueNow = state.retry.filter((e) => e.next_at <= deps.now()).sort((a, b) => a.block - b.block);
  for (const e of dueNow) {
    if (!timeLeft()) break;
    rep.retried++;
    await handle({ dao_id: e.dao_id, space: e.space, chain: e.chain, safe: e.safe }, { tx: e.tx, block: e.block, safeTxHash: e.safe_tx_hash });
  }

  const fins: Record<string, { number: number; timestamp: number }> = {};
  // 3. scan every listed Safe from its checkpoint: every page of get_daos,
  // round robin from where the last run ran out of time
  const daos: Dao[] = [];
  try {
    for (let off = 0; ;) {
      const page = await deps.view<{ total: number; next_offset?: number; done?: boolean; daos: Dao[] }>(addr.registry, "get_daos", [off, PAGE]);
      daos.push(...page.daos);
      const next = page.next_offset ?? off + page.daos.length;
      if (page.done ?? next >= page.total) break;
      if (next <= off) throw new Error(`get_daos did not advance past ${off}`);
      off = next;
    }
  } catch (e) { rep.notes.push("daos unreadable: " + short(e)); }
  rep.daos_watched = daos.length;
  const first = daos.length ? state.cursors.daos % daos.length : 0;
  let scanned = 0;
  for (; scanned < daos.length; scanned++) {
    const d = daos[(first + scanned) % daos.length];
    if (!timeLeft()) { rep.notes.push(`time budget used up before ${d.space}; next run starts there`); break; }
    if (!deps.supported(d.chain)) continue;
    await scan(d);
  }
  state.cursors.daos = daos.length ? (first + scanned) % daos.length : 0;

  // 4. the coverage heartbeat: for each Safe, the last block through which
  // every execution has been handled (filed, already on the registry, or
  // recorded as unmatched). A queued execution holds it back to the block
  // before it, so coverage never claims more than was processed.
  const beats: [number, number, number][] = [];
  const beatKeys: [string, number][] = [];
  for (const d of daos) {
    const sk = safeKey(d.chain, d.safe);
    const cp = state.checkpoints[sk];
    if (!cp) continue;
    const held = state.retry.filter((e) => safeKey(e.chain, e.safe) === sk).reduce((m, e) => Math.min(m, e.block - 1), cp.block);
    if (held < cp.origin || held <= (state.heartbeats[sk] ?? -1)) continue;
    try {
      const t = fins[d.chain]?.number === held ? fins[d.chain].timestamp : await deps.blockTime(d.chain, held);
      beats.push([d.dao_id, held, t]);
      beatKeys.push([sk, held]);
    } catch (e) { rep.notes.push(`${d.space}: block ${held} time unreadable (${short(e)}); heartbeat next run`); }
  }
  for (let i = 0; i < beats.length && rep.writes.length < limits.maxWrites; i += PAGE) {
    const r = await write(addr.registry, "record_coverage", [JSON.stringify(beats.slice(i, i + PAGE))]);
    if (r.ok) for (const [sk, b] of beatKeys.slice(i, i + PAGE)) state.heartbeats[sk] = b;
    rep.heartbeats += r.ok ? Math.min(PAGE, beats.length - i) : 0;
  }

  async function scan(d: Dao) {
    const sk = safeKey(d.chain, d.safe);
    let fin: number;
    try { fins[d.chain] ??= await deps.finalized(d.chain); fin = fins[d.chain].number; } catch (e) { rep.notes.push(`${d.space}: finalized block unreadable (${short(e)})`); return; }
    const cp = state.checkpoints[sk];
    const origin = cp ? cp.origin : Math.max(0, fin - (limits.initialBackfill[d.chain] ?? 0));
    const from = cp ? cp.block + 1 : origin;
    const to = Math.min(fin, from + (limits.maxSpan[d.chain] ?? limits.logChunk) - 1);
    const log: ScanLog = { dao: d.space, chain: d.chain, safe: d.safe.toLowerCase(), from, to, checkpoint: cp?.block ?? -1, events: 0, complete: false };
    rep.scans.push(log);
    if (to < from) { log.complete = true; return; }
    let through = from - 1;
    for (let a = from; a <= to; a += limits.logChunk) {
      const b = Math.min(to, a + limits.logChunk - 1);
      let got: Log[];
      try { got = await deps.logs(d.chain, d.safe, a, b); } catch (e) { rep.notes.push(`${d.space}: logs ${a}-${b} unreadable (${short(e)}); checkpoint held at ${through}`); break; }
      got.sort((x, y) => x.block - y.block);
      for (const lg of got) {
        log.events++;
        rep.executions_seen++;
        await handle(d, lg);
      }
      through = b;
    }
    // every event up to `through` is now processed or queued
    if (through >= from) {
      state.checkpoints[sk] = { block: through, origin, updated: iso() };
      log.checkpoint = through;
    }
    log.complete = through === to;
  }

  state.updated = iso();
  rep.seconds = Math.round(deps.elapsedMs() / 1000);
  return rep;
}
