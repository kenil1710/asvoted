/**
 * The patrol bot, live. The GitHub Action (.github/workflows/patrol.yml)
 * POSTs the durable state from the `patrol-state` branch every 15 minutes with
 * the x-patrol-secret header, and commits the state this returns. Anyone else
 * gets a dry run: the same reads and matching, no transaction, no state.
 *
 * What a run does is in ./patrol/core.ts; this file only wires it to Studio
 * Dev, the Safes' chains and the Snapshot hub. Every write estimates its fee
 * by simulating the call first; what counts as a successful write (FINALIZED,
 * GenVM success, the state change read back) is in ./patrol/txlife.ts. The bot holds a throwaway Studio Dev key
 * (PATROL_KEY) and nothing else.
 */
import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { type CalldataEncodable, type TransactionHash, transactionsStatusNumberToName } from "genlayer-js/types";
import { ADDR } from "./deployments";
import { createPublicClient, fallback, http, type Hex } from "viem";
import { mainnet } from "viem/chains";
import { RPC, SUCCESS, findNonce, rpc } from "./safe";
import { type Proposal, type Sources, decodeExecution, discover } from "./patrol/discover";
import { type Dao, type Deps, type Limits, type Log, type Match, type RunReport, LIMITS, runCore } from "./patrol/core";
import type { TxView } from "./patrol/txlife";
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

/** Log scans may use any endpoint (ExecReader re-reads every execution from its own two RPCs); these allow 9,000-block ranges. */
const LOG_RPC: Record<string, string[]> = {
  ethereum: ["https://ethereum-rpc.publicnode.com"], optimism: ["https://optimism-rpc.publicnode.com"],
  base: ["https://base-rpc.publicnode.com"], polygon: ["https://polygon-bor-rpc.publicnode.com"],
};
async function logRpc<T>(chain: string, method: string, params: unknown[]): Promise<T> {
  for (const url of LOG_RPC[chain] ?? []) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }), signal: AbortSignal.timeout(20_000), cache: "no-store" });
      const j = await r.json();
      if (!j.error) return j.result as T;
    } catch { /* next endpoint */ }
  }
  return rpc<T>(chain, method, params);
}

export interface PatrolOptions {
  dry: boolean;
  key?: string;
  state?: unknown;
  /** another registry than the canonical one (the demo registry) */
  registry?: string;
  /** only these DAO ids */
  only?: number[];
  limits?: Partial<Limits>;
}

export async function runPatrol(opts: PatrolOptions): Promise<{ report: RunReport; state: PatrolState | null }> {
  const t0 = Date.now();
  const chain = studioDevnet;
  const account = opts.key ? createAccount(opts.key as `0x${string}`) : null;
  const read = createClient({ chain });
  const wallet = account ? createClient({ chain, account }) : null;
  const dry = opts.dry || !wallet;
  const registry = opts.registry ?? ADDR.registry;
  const state = loadState(opts.state, registry);

  async function submit(address: string, fn: string, args: CalldataEncodable[], value: bigint): Promise<string> {
    if (!wallet) throw new Error("no signer");
    let fees;
    try {
      const est = await wallet.estimateTransactionFeesForWrite({ address: address as `0x${string}`, functionName: fn, args, value });
      fees = est?.distribution ? { distribution: est.distribution, feeValue: est.feeValue, ...(est.messageAllocations ? { messageAllocations: est.messageAllocations } : {}) } : undefined;
    } catch {
      try { const est = await wallet.estimateTransactionFees(); fees = est?.distribution ? { distribution: est.distribution, feeValue: est.feeValue } : undefined; } catch { fees = undefined; }
    }
    return String(await wallet.writeContract({ address: address as `0x${string}`, functionName: fn, args, value, ...(fees ? { fees } : {}) }));
  }

  /** A transaction as the lifecycle needs it: status name, GenVM result, rollback. */
  async function tx(hash: string): Promise<TxView | null> {
    const t = (await read.getTransaction({ hash: hash as TransactionHash })) as Row | null;
    if (!t) return null;
    const st = (t.statusName ?? t.status) as string | number | undefined;
    const status = typeof st === "number" ? (transactionsStatusNumberToName as Record<number, string>)[st] ?? String(st) : String(st ?? "");
    const rec = ((t.consensus_data as Row)?.leader_receipt as Row[] | undefined)?.[0] as Row | undefined;
    const named = t.txExecutionResultName as string | undefined;
    const exec = named === "FINISHED_WITH_ERROR" ? "ERROR" : (rec?.execution_result as string | undefined) ?? (named === "FINISHED_WITH_RETURN" ? "SUCCESS" : null);
    const result = rec?.result as Row | undefined;
    return { status, exec, rolledBack: result?.status === "rollback", error: typeof result?.payload === "string" ? result.payload : "" };
  }

  const deps: Deps = {
    now: () => Math.floor(Date.now() / 1000),
    elapsedMs: () => Date.now() - t0,
    patrol: account?.address.toLowerCase() ?? "",
    dry,
    addr: { registry, execReader: ADDR.execReader, voteReader: ADDR.voteReader, judge: ADDR.judge },
    async view<T>(address: string, fn: string, args: CalldataEncodable[] = []) {
      const raw = await read.readContract({ address: address as `0x${string}`, functionName: fn, args });
      return (typeof raw === "string" ? (() => { try { return JSON.parse(raw); } catch { return raw; } })() : plain(raw)) as T;
    },
    submit,
    tx,
    sleep: (ms: number) => new Promise((r) => setTimeout(r, ms)),
    async finalized(c: string) {
      const b = await rpc<{ number: string; timestamp: string }>(c, "eth_getBlockByNumber", ["finalized", false]);
      return { number: parseInt(b.number, 16), timestamp: parseInt(b.timestamp, 16) };
    },
    async blockTime(c: string, n: number) {
      const b = await rpc<{ timestamp: string }>(c, "eth_getBlockByNumber", ["0x" + n.toString(16), false]);
      return parseInt(b.timestamp, 16);
    },
    async logs(c: string, safe: string, from: number, to: number): Promise<Log[]> {
      const got = await logRpc<{ transactionHash: string; blockNumber: string; topics: string[]; data: string }[]>(c, "eth_getLogs",
        [{ address: safe, topics: [SUCCESS], fromBlock: "0x" + from.toString(16), toBlock: "0x" + to.toString(16) }]);
      // Safe 1.3 puts the safeTxHash in data, 1.4 indexes it
      return got.map((l) => ({ tx: l.transactionHash.toLowerCase(), block: parseInt(l.blockNumber, 16),
        safeTxHash: (l.topics.length >= 2 ? l.topics[1] : "0x" + l.data.slice(2, 66)).toLowerCase() }));
    },
    match: matchProposal,
    supported: (c: string) => Boolean(RPC[c]),
    ...(opts.only ? { watch: (d: Dao) => opts.only!.includes(d.dao_id) } : {}),
  };
  const report = await runCore(deps, state, { ...LIMITS, ...opts.limits });
  return { report, state: dry ? null : state };
}

const HUB_FIELDS = "ipfs title body choices scores scores_state end";
const ens = createPublicClient({ chain: mainnet, transport: fallback(RPC.ethereum.urls.map((u) => http(u, { timeout: 15_000 }))) });
const tokenMeta = new Map<string, { symbol: string; decimals: number } | null>();

function abiString(hex: string): string {
  const b = hex.slice(2);
  if (b.length === 64) return Buffer.from(b, "hex").toString("utf8").replace(/\0+$/, "");
  const len = parseInt(b.slice(64, 128), 16);
  return Buffer.from(b.slice(128, 128 + len * 2), "hex").toString("utf8");
}

/** The passed proposal this execution implements (./patrol/discover.ts), or why there is none. */
async function matchProposal(d: Dao, lg: Log): Promise<Match> {
  const n = await findNonce(d.chain, d.safe, lg.tx);
  if ("error" in n) return { error: n.error, unmatched: n.error !== "transaction not found" };
  const t = await rpc<{ blockNumber: string; input: Hex }>(d.chain, "eth_getTransactionByHash", [lg.tx]);
  const blk = await rpc<{ timestamp: string }>(d.chain, "eth_getBlockByNumber", [t.blockNumber, false]);
  const when = parseInt(blk.timestamp, 16);
  const src: Sources = {
    async page(space, before, skip, first) {
      const q = `{proposals(first:${first}, skip:${skip}, where:{space:${JSON.stringify(space)}, state:"closed", end_lt:${before}}, orderBy:"end", orderDirection:desc){${HUB_FIELDS}}}`;
      const r = await fetch(HUB, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q }), cache: "no-store", signal: AbortSignal.timeout(20_000) });
      if (!r.ok) throw new Error(`hub answered ${r.status}`);
      const j = await r.json();
      if (j?.errors?.length) throw new Error("hub: " + String(j.errors[0]?.message).slice(0, 80));
      return (j?.data?.proposals ?? []) as Proposal[];
    },
    resolveEns: (name) => ens.getEnsAddress({ name }),
    async token(address) {
      const k = `${d.chain}|${address}`;
      if (!tokenMeta.has(k)) {
        try {
          const [sym, dec] = await Promise.all([rpc<string>(d.chain, "eth_call", [{ to: address, data: "0x95d89b41" }, "latest"]),
            rpc<string>(d.chain, "eth_call", [{ to: address, data: "0x313ce567" }, "latest"])]);
          tokenMeta.set(k, { symbol: abiString(sym), decimals: Number(BigInt(dec)) });
        } catch { tokenMeta.set(k, null); }
      }
      return tokenMeta.get(k) ?? null;
    },
    native: d.chain === "polygon" ? "POL" : "ETH",
  };
  const r = await discover(src, d.space, when, decodeExecution(t.input));
  if ("error" in r) return { error: r.error, unmatched: true };
  return { cid: r.cid, nonce: n.nonce, why: `${r.why} (${r.read} closed proposals read)` };
}
