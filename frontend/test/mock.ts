/**
 * A mocked world for the patrol: Safes' chains (finalized heads, logs), the
 * Studio Dev contracts the patrol reads and writes (registry, readers, judge)
 * and a clock. Pagination follows the registry's contract code: MAX_PAGE
 * records per call and SCAN_CAP records scanned per get_open_checks call.
 */
import type { Dao, Deps, Log, Match } from "../src/lib/patrol/core";
import type { TxView } from "../src/lib/patrol/txlife";

/** How a mocked transaction goes: the statuses successive polls see, and its GenVM result. */
export interface TxPlan { script?: string[]; exec?: "SUCCESS" | "ERROR"; rolledBack?: boolean; noEffect?: boolean; error?: string }

export const MAX_PAGE = 50;
export const SCAN_CAP = 500;
export const PATROL = "0x" + "p".charCodeAt(0).toString(16).repeat(20);

export interface MockCheck {
  check_id: number; dao_id: number; chain: string; safe: string; tx: string; filer: string;
  status: string; round: number; judge_deadline: number; contest_deadline: number; appeal_deadline: number; resp_deadline: number;
  final_verdict?: string;
}

const hex = (n: number, w = 64) => "0x" + n.toString(16).padStart(w, "0");
export const safeAddr = (i: number) => hex(0x5afe0000 + i, 40);
export const txOf = (safe: string, block: number) => "0x" + (safe.slice(-8) + block.toString(16).padStart(8, "0")).padStart(64, "a");
export const safeTxOf = (safe: string, block: number) => "0x" + (safe.slice(-8) + block.toString(16).padStart(8, "0")).padStart(64, "b");

export class World {
  t = 1_800_000_000;
  ms = 0;
  heads: Record<string, number> = { ethereum: 1_000_000 };
  logs: Record<string, Log[]> = {};        // "chain|safe" -> logs
  daos: Dao[] = [];
  checks: MockCheck[] = [];
  execs = new Map<string, number>();       // "chain|safe|tx" -> exec id
  votes = new Map<string, { id: number; read_at: number }>();
  judgments = new Set<string>();
  coverage = new Map<string, { block: number; block_time: number; recorded_at: number }>();           // "check|round"
  writes: { fn: string; args: unknown[]; value: bigint }[] = [];
  views: { fn: string; args: unknown[] }[] = [];
  logCalls: { chain: string; safe: string; from: number; to: number }[] = [];
  failLogs: (chain: string, safe: string, from: number, to: number) => boolean = () => false;
  failMatch: (lg: Log) => string | null = () => null;
  unmatched: (lg: Log) => string | null = () => null;
  failWrite: (fn: string, args: unknown[]) => string | null = () => null;
  plan: (fn: string, args: unknown[]) => TxPlan = () => ({});
  txs = new Map<string, { fn: string; args: unknown[]; script: string[]; exec: string; rolledBack: boolean; error: string; polls: number }>();
  failSubmit = false;
  writeMs = 1000;
  logMs = 0;

  addDao(i: number, chain = "ethereum"): Dao {
    const d = { dao_id: this.daos.length + 1, space: `dao${i}.eth`, chain, safe: safeAddr(i) };
    this.daos.push(d);
    return d;
  }

  addExec(d: Dao, block: number): Log {
    const k = `${d.chain}|${d.safe}`;
    const lg = { tx: txOf(d.safe, block), block, safeTxHash: safeTxOf(d.safe, block) };
    (this.logs[k] ??= []).push(lg);
    return lg;
  }

  addCheck(c: Partial<MockCheck>): MockCheck {
    const x: MockCheck = { check_id: this.checks.length + 1, dao_id: 1, chain: "ethereum", safe: safeAddr(0), tx: hex(this.checks.length + 1),
      filer: PATROL, status: "FINAL", round: 0, judge_deadline: 0, contest_deadline: 0, appeal_deadline: 0, resp_deadline: 0, ...c };
    this.checks.push(x);
    return x;
  }

  /** the transaction of every file_check sent, in order (a repeat would be a double filing) */
  filedTxs(): string[] {
    const byId = new Map([...this.execs.entries()].map(([k, v]) => [v, k.split("|")[2]]));
    return this.writes.filter((w) => w.fn === "file_check").map((w) => byId.get(Number(w.args[1]))!);
  }

  view(fn: string, args: unknown[]): unknown {
    this.views.push({ fn, args });
    const a = args as never[];
    switch (fn) {
      case "get_daos": {
        const o = Math.max(Number(a[0]), 0), lim = Math.min(Number(a[1]), MAX_PAGE);
        return { total: this.daos.length, daos: this.daos.slice(o, o + lim) };
      }
      case "get_open_checks": {
        const o = Math.max(Number(a[0]), 0), lim = Math.min(Number(a[1]), MAX_PAGE);
        const out = []; let i = o + 1, scanned = 0;
        while (i <= this.checks.length && out.length < lim && scanned < SCAN_CAP) {
          const c = this.checks[i - 1]; scanned++;
          if (["PROVISIONAL", "CONTESTABLE", "APPEALED"].includes(c.status)) {
            const active = c.status === "PROVISIONAL" ? c.judge_deadline : c.status === "CONTESTABLE" ? c.contest_deadline : c.round === 2 ? c.resp_deadline : c.appeal_deadline;
            out.push({ check_id: c.check_id, status: c.status, round: c.round, filer: c.filer, judge_deadline: c.judge_deadline,
              contest_deadline: c.contest_deadline, appeal_deadline: c.appeal_deadline, resp_deadline: c.resp_deadline, active_deadline: active });
          }
          i++;
        }
        return { next_offset: i - 1, done: i > this.checks.length, checks: out };
      }
      case "get_check_id_by_tx": return this.checks.find((c) => c.chain === a[0] && c.safe === String(a[1]).toLowerCase() && c.tx === a[2])?.check_id ?? 0;
      case "get_check": { const c = this.checks[Number(a[0]) - 1]; return c ? { found: true, ...c } : { found: false }; }
      case "get_execution_id": return this.execs.get(`${a[0]}|${String(a[1]).toLowerCase()}|${a[2]}`) ?? 0;
      case "get_execution": return { found: true, l1_block: 0 };
      case "get_proposal_id": return this.votes.get(String(a[0]))?.id ?? 0;
      case "get_proposal": { const v = [...this.votes.values()].find((x) => x.id === Number(a[0])); return { found: !!v, read_at: v?.read_at ?? 0, ens_names: [] }; }
      case "get_names_at": return { found: true };
      case "get_judgment": return { found: this.judgments.has(`${a[1]}|${a[2]}`) };
      case "get_coverage": { const c = this.coverage.get(`${a[0]}|${a[1]}`); return c ? { found: true, ...c } : { found: false }; }
    }
    throw new Error("mock: no view " + fn);
  }

  submit(fn: string, args: unknown[], value: bigint): string {
    if (this.failSubmit) throw new Error("rpc down");
    this.ms += this.writeMs;
    this.writes.push({ fn, args, value });
    const hash = hex(0x7000 + this.writes.length);
    const err = this.failWrite(fn, args);
    const p = err ? { exec: "ERROR" as const, error: err, noEffect: true } : this.plan(fn, args);
    const exec = p.exec ?? "SUCCESS";
    this.txs.set(hash, { fn, args, script: p.script ?? ["FINALIZED"], exec, rolledBack: !!p.rolledBack, error: p.error ?? "", polls: 0 });
    if (exec === "SUCCESS" && !p.rolledBack && !p.noEffect) this.apply(fn, args);
    return hash;
  }

  txView(hash: string): TxView | null {
    const t = this.txs.get(hash);
    if (!t) return null;
    const status = t.script[Math.min(t.polls, t.script.length - 1)];
    t.polls++;
    return { status, exec: t.exec, rolledBack: t.rolledBack, error: t.error };
  }

  private apply(fn: string, args: unknown[]) {
    const a = args as never[];
    switch (fn) {
      case "read_execution": if (!this.execs.has(`${a[0]}|${String(a[1]).toLowerCase()}|${a[2]}`)) this.execs.set(`${a[0]}|${String(a[1]).toLowerCase()}|${a[2]}`, this.execs.size + 1); break;
      case "read_proposal": this.votes.set(String(a[0]), { id: this.votes.get(String(a[0]))?.id ?? this.votes.size + 1, read_at: this.t }); break;
      case "file_check": {
        const [daoId, execId] = [Number(a[0]), Number(a[1])];
        const key = [...this.execs.entries()].find(([, v]) => v === execId)![0].split("|");
        // the registry refuses a second check of one execution (payable: ok:false, no new check)
        if (!this.checks.some((c) => c.tx === key[2] && c.safe === key[1])) this.addCheck({ dao_id: daoId, chain: key[0], safe: key[1], tx: key[2], filer: PATROL, status: "PROVISIONAL", judge_deadline: this.t + 86400 });
        break;
      }
      case "judge": this.judgments.add(`${a[1]}|${this.checks[Number(a[1]) - 1].round}`); break;
      case "rule": { const c = this.checks[Number(a[0]) - 1]; c.status = c.round === 2 ? "FINAL" : "CONTESTABLE"; c.contest_deadline = this.t + 21600; break; }
      case "record_coverage":
        for (const [dao, block, block_time] of JSON.parse(String(a[0])) as number[][]) {
          const prev = this.coverage.get(`${dao}|${PATROL}`);
          if (!prev || block > prev.block) this.coverage.set(`${dao}|${PATROL}`, { block, block_time, recorded_at: this.t });
        }
        break;
      case "finalize": case "expire": this.checks[Number(a[0]) - 1].status = "FINAL"; break;
    }
  }

  deps(over: Partial<Deps> = {}): Deps {
    return {
      now: () => this.t,
      elapsedMs: () => this.ms,
      patrol: PATROL,
      dry: false,
      addr: { registry: "0xregistry", execReader: "0xexec", voteReader: "0xvote", judge: "0xjudge" },
      view: async <T,>(_addr: string, fn: string, args: unknown[] = []) => this.view(fn, args) as T,
      submit: async (_addr: string, fn: string, args: unknown[], value: bigint) => this.submit(fn, args, value),
      tx: async (hash: string) => this.txView(hash),
      sleep: async (ms: number) => { this.ms += ms; },
      finalized: async (c: string) => ({ number: this.heads[c], timestamp: this.t - 900 }),
      blockTime: async (c: string, n: number) => this.t - 900 - (this.heads[c] - n) * 12,
      logs: async (c: string, safe: string, from: number, to: number) => {
        this.logCalls.push({ chain: c, safe, from, to });
        this.ms += this.logMs;
        if (this.failLogs(c, safe, from, to)) throw new Error("rpc down");
        return (this.logs[`${c}|${safe}`] ?? []).filter((l) => l.block >= from && l.block <= to);
      },
      match: async (_d: Dao, lg: Log): Promise<Match> => {
        const f = this.failMatch(lg);
        if (f) return { error: f, unmatched: false };
        const u = this.unmatched(lg);
        if (u) return { error: u, unmatched: true };
        return { cid: "cid-" + lg.tx.slice(-6), nonce: 1, why: "test match" };
      },
      supported: () => true,
      ...over,
    };
  }
}
