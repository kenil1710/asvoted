/**
 * The life of one patrol transaction. ACCEPTED is never success:
 *
 *   1. before sending, the expected state change is read; if it already
 *      holds (an earlier transaction landed, or someone else did it), nothing
 *      is sent;
 *   2. an operation with a stored hash in state.pending is never sent again:
 *      that hash is followed instead (a run that ended while it was in
 *      flight left it there);
 *   3. a new transaction's hash goes into state.pending as soon as it is
 *      known;
 *   4. success = status FINALIZED, GenVM execution SUCCESS and no rollback,
 *      and then the expected state change read back from the contracts
 *      (a payable call such as file_check can finish without error and
 *      still refuse: only the registry says whether a check exists);
 *   5. FINALIZED with an error, UNDETERMINED or CANCELED is a failure; a
 *      transaction still short of FINALIZED when the run's time is up stays
 *      in state.pending, uncertain, and the next run resumes it;
 *   6. reconciliation: a stored hash the node has no record of is checked
 *      against the chain itself: the expected change there means it landed;
 *      none after LOST_AFTER_S means it is lost (and the operation may be
 *      sent again, after the same read-first check).
 */
import type { CalldataEncodable } from "genlayer-js/types";
import type { PatrolState } from "./state";

export type Expect =
  | { kind: "exec_id"; chain: string; safe: string; tx: string }
  | { kind: "fresh_vote"; cid: string; chain: string; safe: string; after: number }
  | { kind: "names"; vote_id: number; l1: number }
  | { kind: "check_by_tx"; chain: string; safe: string; tx: string }
  | { kind: "judgment"; check_id: number; round: number }
  | { kind: "check_moved"; check_id: number; status: string; round: number }
  | { kind: "coverage"; reporter: string; entries: [number, number][] };

export interface PendingTx {
  id: string;              // the operation; one in flight per id
  address: string;
  fn: string;
  args: string;            // JSON
  value: string;
  hash: string;
  submitted_at: number;
  polls: number;
  expect: Expect;
}

export interface TxView { status: string; exec: string | null; rolledBack: boolean; error: string }
export interface TxOutcome { ok: boolean; hash: string | null; note: string; dry?: boolean; uncertain?: boolean; skipped?: boolean }

export interface ChainIO {
  dry: boolean;
  now(): number;
  elapsedMs(): number;
  sleep(ms: number): Promise<void>;
  view<T>(address: string, fn: string, args?: CalldataEncodable[]): Promise<T>;
  submit(address: string, fn: string, args: CalldataEncodable[], value: bigint): Promise<string>;
  tx(hash: string): Promise<TxView | null>;
}

export interface Addrs { registry: string; execReader: string; voteReader: string; judge: string }
export const POLL_MS = 4_000;
/** a hash the node has no record of this long after it was sent is given up */
export const LOST_AFTER_S = 1800;
const TX_LOG_MAX = 200;

/** Whether the change a transaction was sent to make is now on chain. */
export async function holds(io: ChainIO, a: Addrs, e: Expect): Promise<boolean> {
  switch (e.kind) {
    case "exec_id": return Number(await io.view<number>(a.execReader, "get_execution_id", [e.chain, e.safe, e.tx])) > 0;
    case "fresh_vote": {
      const id = Number(await io.view<number>(a.voteReader, "get_proposal_id", [e.cid, e.chain, e.safe]));
      if (!id) return false;
      return Number((await io.view<{ read_at: number }>(a.voteReader, "get_proposal", [id])).read_at) >= e.after;
    }
    case "names": return Boolean((await io.view<{ found: boolean }>(a.voteReader, "get_names_at", [e.vote_id, e.l1])).found);
    case "check_by_tx": return Number(await io.view<number>(a.registry, "get_check_id_by_tx", [e.chain, e.safe, e.tx])) > 0;
    case "judgment": return Boolean((await io.view<{ found: boolean }>(a.judge, "get_judgment", [a.registry, e.check_id, e.round])).found);
    case "check_moved": {
      const c = await io.view<{ found: boolean; status: string; round: number }>(a.registry, "get_check", [e.check_id]);
      return Boolean(c.found) && (c.status !== e.status || Number(c.round) !== e.round);
    }
    case "coverage": {
      for (const [dao, block] of e.entries) {
        const c = await io.view<{ found: boolean; block?: number }>(a.registry, "get_coverage", [dao, e.reporter]);
        if (!c.found || Number(c.block) < block) return false;
      }
      return true;
    }
  }
}

export class Lifecycle {
  sent = 0;
  constructor(private io: ChainIO, private a: Addrs, private state: PatrolState, private deadlineMs: number) {}

  private log(p: PendingTx, outcome: string) {
    this.state.tx_log.push({ id: p.id, fn: p.fn, hash: p.hash, outcome, at: new Date(this.io.now() * 1000).toISOString() });
    if (this.state.tx_log.length > TX_LOG_MAX) this.state.tx_log.splice(0, this.state.tx_log.length - TX_LOG_MAX);
  }
  private drop(id: string) { this.state.pending = this.state.pending.filter((p) => p.id !== id); }

  /** Follows a stored transaction until it is decided or the run's time is up. */
  async follow(p: PendingTx, untilMs = this.deadlineMs): Promise<TxOutcome> {
    for (;;) {
      let v: TxView | null = null;
      try { v = await this.io.tx(p.hash); } catch { v = null; }
      p.polls++;
      if (!v) {
        // the node knows no such transaction: reconcile with the chain itself
        let landed = false;
        try { landed = await holds(this.io, this.a, p.expect); } catch { landed = false; }
        if (landed) {
          this.drop(p.id);
          this.log(p, "unknown to the node; expected change found on chain");
          return { ok: true, hash: p.hash, note: "reconciled: the expected change is on chain" };
        }
        if (this.io.now() - p.submitted_at > LOST_AFTER_S) {
          this.drop(p.id);
          this.log(p, "lost");
          return { ok: false, hash: p.hash, note: `no record of the transaction ${LOST_AFTER_S} s after it was sent, and no change on chain` };
        }
      }
      if (v) {
        if (v.status === "FINALIZED") {
          this.drop(p.id);
          if (v.exec !== "SUCCESS" || v.rolledBack) {
            this.log(p, "failed: " + (v.error || v.exec || "rollback"));
            return { ok: false, hash: p.hash, note: `FINALIZED with ${v.rolledBack ? "rollback" : v.exec ?? "no result"}${v.error ? ": " + v.error.slice(0, 100) : ""}` };
          }
          let ok = false;
          try { ok = await holds(this.io, this.a, p.expect); } catch { ok = false; }
          this.log(p, ok ? "finalized, verified" : "finalized, expected change not found");
          return ok ? { ok: true, hash: p.hash, note: "FINALIZED, verified" }
            : { ok: false, hash: p.hash, note: "FINALIZED but the expected state change is not on chain" };
        }
        if (v.status === "UNDETERMINED" || v.status === "CANCELED") {
          this.drop(p.id);
          this.log(p, v.status);
          return { ok: false, hash: p.hash, note: v.status };
        }
      }
      if (this.io.elapsedMs() >= untilMs) {
        return { ok: false, hash: p.hash, uncertain: true, note: `${v?.status ?? "unreadable"} when the run ended; resumed next run from the stored hash` };
      }
      await this.io.sleep(POLL_MS);
    }
  }

  /** Sends (or resumes) one operation and reports its verified outcome. */
  async send(id: string, address: string, fn: string, args: CalldataEncodable[], value: bigint, expect: Expect): Promise<TxOutcome> {
    const stored = this.state.pending.find((p) => p.id === id);
    if (stored) return this.follow(stored);
    try {
      if (await holds(this.io, this.a, expect)) return { ok: true, hash: null, note: "already on chain; not sent", skipped: true };
    } catch { /* unreadable: send, and verify after */ }
    if (this.io.dry) return { ok: false, hash: null, note: "dry run: not sent", dry: true };
    let hash: string;
    try { hash = await this.io.submit(address, fn, args, value); } catch (e) {
      return { ok: false, hash: null, note: "submit failed: " + String((e as Error)?.message ?? e).slice(0, 140) };
    }
    this.sent++;
    const p: PendingTx = { id, address, fn, args: JSON.stringify(args, (_k, v) => (typeof v === "bigint" ? v.toString() : v)), value: value.toString(),
      hash, submitted_at: this.io.now(), polls: 0, expect };
    this.state.pending.push(p);
    return this.follow(p);
  }

  /** Every stored transaction from earlier runs, followed for up to `eachMs` more. */
  async resumeAll(eachMs: number): Promise<{ p: PendingTx; outcome: TxOutcome }[]> {
    const out = [];
    for (const p of [...this.state.pending]) {
      out.push({ p, outcome: await this.follow(p, Math.min(this.deadlineMs, this.io.elapsedMs() + eachMs)) });
    }
    return out;
  }
}
