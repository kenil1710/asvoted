/**
 * The patrol bot, live. The GitHub Action (.github/workflows/patrol.yml)
 * POSTs the durable state from the `patrol-state` branch every 15 minutes with
 * the x-patrol-secret header, and commits the state this returns. Anyone else
 * gets a dry run: the same reads and matching, no transaction, no state.
 *
 * What a run does is in ./patrol/core.ts; this file only wires it to Studio
 * Dev, the Safes' chains and the Snapshot hub. Every write estimates its fee
 * by simulating the call first. The bot holds a throwaway Studio Dev key
 * (PATROL_KEY) and nothing else.
 */
import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import type { CalldataEncodable, TransactionHash } from "genlayer-js/types";
import { ADDR } from "./deployments";
import { RPC, SUCCESS, findNonce, rpc } from "./safe";
import { type Dao, type Deps, type Log, type Match, type RunReport, type WriteResult, runCore } from "./patrol/core";
import { type PatrolState, loadState } from "./patrol/state";

export type { RunReport } from "./patrol/core";

const HUB = "https://hub.snapshot.org/graphql";
type Row = Record<string, unknown>;

const plain = (v: unknown): unknown => {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v);
  return v;
};

export async function runPatrol(opts: { dry: boolean; key?: string; state?: unknown }): Promise<{ report: RunReport; state: PatrolState | null }> {
  const t0 = Date.now();
  const chain = studioDevnet;
  const account = opts.key ? createAccount(opts.key as `0x${string}`) : null;
  const read = createClient({ chain });
  const wallet = account ? createClient({ chain, account }) : null;
  const dry = opts.dry || !wallet;
  const state = loadState(opts.state);

  async function write(address: string, fn: string, args: CalldataEncodable[], value = 0n): Promise<WriteResult> {
    if (dry || !wallet) return { ok: false, hash: null, note: "dry run: not sent", dry: true };
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
          return { ok, hash, note: ok ? String(name) : reverted ? "reverted: " + String((rec?.result as Row)?.payload ?? "").slice(0, 120) : String(name) };
        }
        if (Date.now() - t0 > 280_000) break;
      }
      return { ok: false, hash, note: "still pending when the run ended; next run picks it up" };
    } catch (e) {
      return { ok: false, hash, note: String((e as Error).message ?? e).slice(0, 160) };
    }
  }

  const deps: Deps = {
    now: () => Math.floor(Date.now() / 1000),
    elapsedMs: () => Date.now() - t0,
    patrol: account?.address.toLowerCase() ?? "",
    dry,
    addr: { registry: ADDR.registry, execReader: ADDR.execReader, voteReader: ADDR.voteReader, judge: ADDR.judge },
    async view<T>(address: string, fn: string, args: CalldataEncodable[] = []) {
      const raw = await read.readContract({ address: address as `0x${string}`, functionName: fn, args });
      return (typeof raw === "string" ? (() => { try { return JSON.parse(raw); } catch { return raw; } })() : plain(raw)) as T;
    },
    write,
    async finalized(c: string) {
      const b = await rpc<{ number: string; timestamp: string }>(c, "eth_getBlockByNumber", ["finalized", false]);
      return { number: parseInt(b.number, 16), timestamp: parseInt(b.timestamp, 16) };
    },
    async logs(c: string, safe: string, from: number, to: number): Promise<Log[]> {
      const got = await rpc<{ transactionHash: string; blockNumber: string; topics: string[]; data: string }[]>(c, "eth_getLogs",
        [{ address: safe, topics: [SUCCESS], fromBlock: "0x" + from.toString(16), toBlock: "0x" + to.toString(16) }]);
      // Safe 1.3 puts the safeTxHash in data, 1.4 indexes it
      return got.map((l) => ({ tx: l.transactionHash.toLowerCase(), block: parseInt(l.blockNumber, 16),
        safeTxHash: (l.topics.length >= 2 ? l.topics[1] : "0x" + l.data.slice(2, 66)).toLowerCase() }));
    },
    match: matchProposal,
    supported: (c: string) => Boolean(RPC[c]),
  };
  const report = await runCore(deps, state);
  return { report, state: dry ? null : state };
}

/** The most recent passed proposal of the space that ended before the execution, preferring one that names an address it touches. */
async function matchProposal(d: Dao, lg: Log): Promise<Match> {
  const tx = lg.tx;
  const n = await findNonce(d.chain, d.safe, tx);
  if ("error" in n) return { error: n.error, unmatched: n.error !== "transaction not found" };
  const t = await rpc<{ blockNumber: string; input: string }>(d.chain, "eth_getTransactionByHash", [tx]);
  const blk = await rpc<{ timestamp: string }>(d.chain, "eth_getBlockByNumber", [t.blockNumber, false]);
  const when = parseInt(blk.timestamp, 16);
  const touched = new Set((t.input.toLowerCase().match(/[0-9a-f]{64}/g) ?? []).filter((w) => w.startsWith("000000000000000000000000") && !w.startsWith("0000000000000000000000000000")).map((w) => "0x" + w.slice(24)));
  const q = `{proposals(first:25, where:{space:"${d.space}", state:"closed", end_lt:${when}}, orderBy:"end", orderDirection:desc){ipfs body type choices scores scores_state end}}`;
  const r = await fetch(HUB, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q }), cache: "no-store" });
  if (!r.ok) return { error: `hub answered ${r.status}`, unmatched: false };
  const rows = ((await r.json())?.data?.proposals ?? []) as { ipfs: string; body: string; type: string; choices: string[]; scores: number[]; scores_state: string; end: number }[];
  const passed = rows.filter((p) => p.scores_state === "final" && p.scores.length === p.choices.length && p.scores.length > 0 && (() => {
    const best = p.scores.indexOf(Math.max(...p.scores));
    const label = (p.choices[best] ?? "").toLowerCase().replace(/^[^a-z]+/, "");
    return /^(for|yes|yae|yay|aye|approve|accept|in favou?r|support|agree|pass|execute|enable|fund|adopt|ratify|confirm)\b/.test(label);
  })());
  if (passed.length === 0) return { error: "no passed proposal of the space ended before it", unmatched: true };
  const naming = passed.find((p) => [...touched].some((a) => p.body.toLowerCase().includes(a)));
  if (naming) return { cid: naming.ipfs, nonce: n.nonce, why: "most recent passed proposal naming an address the execution touches" };
  // No passed proposal names anything this execution touches: filing against
  // the latest one would mostly measure the bot's guess, not the signers.
  return { error: "no passed proposal of the space names an address this execution touches; not filed", unmatched: true };
}
