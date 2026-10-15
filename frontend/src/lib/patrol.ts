/**
 * The patrol bot. Called by cron-job.org every 15 minutes (with the
 * x-patrol-secret header) and by anyone else as a dry run.
 *
 * One run, bounded by MAX_WRITES transactions and TIME_BUDGET_MS:
 *   1. close its own filings: rule what is judged, judge what is not, finalize
 *      what is past its contest window, expire what is past a deadline;
 *   2. for every DAO listed on the CANONICAL registry, read the Safe's
 *      ExecutionSuccess logs from the last LOOKBACK_S on its chain;
 *   3. skip executions that already have a check (precedent: one check per
 *      (Safe, tx), never re-filed) or that are not finalized yet;
 *   4. match each new one to the most recent PASSED proposal of the DAO's
 *      space that ended before it and whose text names an address the
 *      execution touches (no such proposal: not filed, noted in the report);
 *   5. file it: ExecReader.read_execution -> VoteReader.read_proposal ->
 *      file_check (+0.1 GEN) -> judge -> rule, one step per write, resuming
 *      next run where it stopped.
 * Every write estimates its fee by simulating the call first.
 * The bot holds a throwaway Studio Dev key (PATROL_KEY) and nothing else.
 */
import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import type { CalldataEncodable, TransactionHash } from "genlayer-js/types";
import { ADDR } from "./deployments";
import { RPC, SUCCESS, findNonce, rpc } from "./safe";

const STAKE = 10n ** 17n;
const MAX_WRITES = 5;
const TIME_BUDGET_MS = 240_000;
const LOOKBACK_S = 3 * 3600;
const BLOCK_S: Record<string, number> = { ethereum: 12, arbitrum: 0.25, optimism: 2, base: 2, polygon: 2 };
const LOG_CHUNK = 9_000;
const HUB = "https://hub.snapshot.org/graphql";

type Row = Record<string, unknown>;
export interface RunReport {
  started: string;
  dry_run: boolean;
  patrol: string;
  registry: string;
  writes: { fn: string; args: string; ok: boolean; hash: string | null; note: string }[];
  daos_watched: number;
  executions_seen: number;
  already_checked: number;
  not_final_yet: number;
  matched: { tx: string; dao: string; cid: string; why: string }[];
  closed: string[];
  notes: string[];
  seconds: number;
}

const plain = (v: unknown): unknown => {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v);
  return v;
};

export async function runPatrol(opts: { dry: boolean; key?: string }): Promise<RunReport> {
  const t0 = Date.now();
  const chain = studioDevnet;
  const account = opts.key ? createAccount(opts.key as `0x${string}`) : null;
  const read = createClient({ chain });
  const wallet = account ? createClient({ chain, account }) : null;
  const dry = opts.dry || !wallet;
  const rep: RunReport = { started: new Date().toISOString(), dry_run: dry, patrol: account?.address.toLowerCase() ?? "", registry: ADDR.registry,
    writes: [], daos_watched: 0, executions_seen: 0, already_checked: 0, not_final_yet: 0, matched: [], closed: [], notes: [], seconds: 0 };
  const view = async <T,>(address: string, fn: string, args: CalldataEncodable[] = []) => {
    const raw = await read.readContract({ address: address as `0x${string}`, functionName: fn, args });
    return (typeof raw === "string" ? (() => { try { return JSON.parse(raw); } catch { return raw; } })() : plain(raw)) as T;
  };
  const budgetLeft = () => rep.writes.length < MAX_WRITES && Date.now() - t0 < TIME_BUDGET_MS;

  async function write(address: string, fn: string, args: CalldataEncodable[], value = 0n): Promise<boolean> {
    if (dry || !wallet) { rep.writes.push({ fn, args: JSON.stringify(args).slice(0, 160), ok: false, hash: null, note: "dry run: not sent" }); return false; }
    let fees;
    try {
      const est = await wallet.estimateTransactionFeesForWrite({ address: address as `0x${string}`, functionName: fn, args, value });
      fees = est?.distribution ? { distribution: est.distribution, feeValue: est.feeValue, ...(est.messageAllocations ? { messageAllocations: est.messageAllocations } : {}) } : undefined;
    } catch {
      try { const est = await wallet.estimateTransactionFees(); fees = est?.distribution ? { distribution: est.distribution, feeValue: est.feeValue } : undefined; } catch { fees = undefined; }
    }
    let hash: string | null = null;
    try {
      hash = await wallet.writeContract({ address: address as `0x${string}`, functionName: fn, args, value, ...(fees ? { fees } : {}) });
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const tx = (await read.getTransaction({ hash: hash as TransactionHash }).catch(() => null)) as Row | null;
        const st = (tx?.statusName ?? tx?.status) as string | number | undefined;
        const name = typeof st === "number" ? ["PENDING", "PROPOSING", "COMMITTING", "REVEALING", "ACCEPTED", "FINALIZED", "UNDETERMINED", "CANCELED"][st] : st;
        if (name === "ACCEPTED" || name === "FINALIZED" || name === "UNDETERMINED" || name === "CANCELED") {
          const rec = ((tx?.consensus_data as Row)?.leader_receipt as Row[] | undefined)?.[0] as Row | undefined;
          const reverted = rec?.execution_result === "ERROR" || (rec?.result as Row)?.status === "rollback";
          const ok = (name === "ACCEPTED" || name === "FINALIZED") && !reverted;
          rep.writes.push({ fn, args: JSON.stringify(args).slice(0, 160), ok, hash, note: ok ? String(name) : reverted ? "reverted: " + String((rec?.result as Row)?.payload ?? "").slice(0, 120) : String(name) });
          return ok;
        }
        if (Date.now() - t0 > TIME_BUDGET_MS + 40_000) break;
      }
      rep.writes.push({ fn, args: JSON.stringify(args).slice(0, 160), ok: false, hash, note: "still pending when the run ended; next run picks it up" });
    } catch (e) {
      rep.writes.push({ fn, args: JSON.stringify(args).slice(0, 160), ok: false, hash, note: String((e as Error).message ?? e).slice(0, 160) });
    }
    return false;
  }

  const now = Math.floor(Date.now() / 1000);
  // 1. close our own filings
  try {
    const open = await view<{ checks: { check_id: number; status: string; round: number; filer: string; judge_deadline: number; contest_deadline: number; appeal_deadline: number }[] }>(ADDR.registry, "get_open_checks", [0, 50]);
    for (const c of open.checks) {
      if (!budgetLeft()) break;
      if (!rep.patrol || c.filer !== rep.patrol) continue;
      if (c.status === "CONTESTABLE" && now > c.contest_deadline) { rep.closed.push(`finalize #${c.check_id}`); await write(ADDR.registry, "finalize", [c.check_id]); continue; }
      if ((c.status === "PROVISIONAL" && now > c.judge_deadline) || (c.status === "APPEALED" && now > c.appeal_deadline)) { rep.closed.push(`expire #${c.check_id}`); await write(ADDR.registry, "expire", [c.check_id]); continue; }
      if (c.status === "PROVISIONAL" || c.status === "APPEALED") {
        const j = await view<{ found: boolean }>(ADDR.judge, "get_judgment", [ADDR.registry, c.check_id, c.round]);
        if (!j.found) { rep.closed.push(`judge #${c.check_id}`); if (!(await write(ADDR.judge, "judge", [ADDR.registry, c.check_id]))) continue; }
        if (budgetLeft()) { rep.closed.push(`rule #${c.check_id}`); await write(ADDR.registry, "rule", [c.check_id]); }
      }
    }
  } catch (e) { rep.notes.push("open checks unreadable: " + String((e as Error).message).slice(0, 100)); }

  // 2-5. watch the listed Safes
  let daos: { dao_id: number; space: string; chain: string; safe: string }[] = [];
  try { daos = (await view<{ daos: typeof daos }>(ADDR.registry, "get_daos", [0, 50])).daos; } catch (e) { rep.notes.push("daos unreadable: " + String((e as Error).message).slice(0, 100)); }
  rep.daos_watched = daos.length;
  for (const d of daos) {
    if (Date.now() - t0 > TIME_BUDGET_MS) break;
    if (!RPC[d.chain]) continue;
    let logs: { transactionHash: string; blockNumber: string }[] = [];
    let finalized = 0;
    try {
      const head = parseInt(await rpc<string>(d.chain, "eth_blockNumber", []), 16);
      finalized = parseInt((await rpc<{ number: string }>(d.chain, "eth_getBlockByNumber", ["finalized", false])).number, 16);
      const from = Math.max(0, head - Math.ceil(LOOKBACK_S / BLOCK_S[d.chain]));
      for (let a = from; a <= head; a += LOG_CHUNK) {
        const got = await rpc<typeof logs>(d.chain, "eth_getLogs", [{ address: d.safe, topics: [SUCCESS], fromBlock: "0x" + a.toString(16), toBlock: "0x" + Math.min(head, a + LOG_CHUNK - 1).toString(16) }]);
        logs = logs.concat(got);
      }
    } catch (e) { rep.notes.push(`${d.space}: logs unreadable (${String((e as Error).message).slice(0, 80)})`); continue; }
    for (const lg of logs) {
      rep.executions_seen++;
      const tx = lg.transactionHash.toLowerCase();
      const existing = Number(await view<number>(ADDR.registry, "get_check_id_by_tx", [d.chain, d.safe, tx]));
      if (existing) { rep.already_checked++; continue; }
      if (parseInt(lg.blockNumber, 16) > finalized) { rep.not_final_yet++; continue; }
      if (!budgetLeft()) { rep.notes.push(`budget used up before ${tx.slice(0, 10)}; next run`); continue; }
      const m = await matchProposal(d, tx);
      if ("error" in m) { rep.notes.push(`${d.space} ${tx.slice(0, 10)}: ${m.error}`); continue; }
      rep.matched.push({ tx, dao: d.space, cid: m.cid, why: m.why });
      let execId = Number(await view<number>(ADDR.execReader, "get_execution_id", [d.chain, d.safe, tx]));
      if (!execId) {
        if (!(await write(ADDR.execReader, "read_execution", [d.chain, d.safe, tx, m.nonce]))) continue;
        execId = Number(await view<number>(ADDR.execReader, "get_execution_id", [d.chain, d.safe, tx]));
      }
      if (!budgetLeft()) continue;
      let voteId = Number(await view<number>(ADDR.voteReader, "get_proposal_id", [m.cid, d.chain, d.safe]));
      const v = voteId ? await view<{ read_at: number }>(ADDR.voteReader, "get_proposal", [voteId]) : null;
      if (!v || now - v.read_at > 3000) {
        if (!(await write(ADDR.voteReader, "read_proposal", [m.cid, d.chain, d.safe]))) continue;
        voteId = Number(await view<number>(ADDR.voteReader, "get_proposal_id", [m.cid, d.chain, d.safe]));
      }
      if (!budgetLeft()) continue;
      await write(ADDR.registry, "file_check", [d.dao_id, execId, voteId, `patrol: ${m.why}`.slice(0, 200)], STAKE);
    }
  }
  rep.seconds = Math.round((Date.now() - t0) / 1000);
  return rep;
}

/** The most recent passed proposal of the space that ended before the execution, preferring one that names an address it touches. */
async function matchProposal(d: { space: string; chain: string; safe: string }, tx: string): Promise<{ cid: string; nonce: number; why: string } | { error: string }> {
  const n = await findNonce(d.chain, d.safe, tx);
  if ("error" in n) return { error: n.error };
  const t = await rpc<{ blockNumber: string; input: string }>(d.chain, "eth_getTransactionByHash", [tx]);
  const blk = await rpc<{ timestamp: string }>(d.chain, "eth_getBlockByNumber", [t.blockNumber, false]);
  const when = parseInt(blk.timestamp, 16);
  const touched = new Set((t.input.toLowerCase().match(/[0-9a-f]{64}/g) ?? []).filter((w) => w.startsWith("000000000000000000000000") && !w.startsWith("0000000000000000000000000000")).map((w) => "0x" + w.slice(24)));
  const q = `{proposals(first:25, where:{space:"${d.space}", state:"closed", end_lt:${when}}, orderBy:"end", orderDirection:desc){ipfs body type choices scores scores_state end}}`;
  const r = await fetch(HUB, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q }), cache: "no-store" });
  const rows = ((await r.json())?.data?.proposals ?? []) as { ipfs: string; body: string; type: string; choices: string[]; scores: number[]; scores_state: string; end: number }[];
  const passed = rows.filter((p) => p.scores_state === "final" && p.scores.length === p.choices.length && p.scores.length > 0 && (() => {
    const best = p.scores.indexOf(Math.max(...p.scores));
    const label = (p.choices[best] ?? "").toLowerCase().replace(/^[^a-z]+/, "");
    return /^(for|yes|yae|yay|aye|approve|accept|in favou?r|support|agree|pass|execute|enable|fund|adopt|ratify|confirm)\b/.test(label);
  })());
  if (passed.length === 0) return { error: "no passed proposal of the space ended before it" };
  const naming = passed.find((p) => [...touched].some((a) => p.body.toLowerCase().includes(a)));
  if (naming) return { cid: naming.ipfs, nonce: n.nonce, why: "most recent passed proposal naming an address the execution touches" };
  // No passed proposal names anything this execution touches: filing against
  // the latest one would mostly measure the bot's guess, not the signers.
  return { error: "no passed proposal of the space names an address this execution touches; not filed" };
}
