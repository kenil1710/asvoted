/**
 * Server-side helpers shared by /api/nonce and the patrol bot.
 *
 * The Safe nonce a transaction used is a HINT: ExecReader recomputes the Safe
 * transaction hash from it and refuses a wrong one. It is found here by
 * reading the receipt's ExecutionSuccess hash and recomputing candidates from
 * the Safe's nonce at the transaction's block downward.
 */
import { decodeFunctionData, encodeAbiParameters, keccak256, parseAbi, type Hex } from "viem";

export const RPC: Record<string, { id: number; urls: string[] }> = {
  ethereum: { id: 1, urls: ["https://eth-pokt.nodies.app", "https://rpc.mevblocker.io"] },
  arbitrum: { id: 42161, urls: ["https://arb1.arbitrum.io/rpc", "https://arb-pokt.nodies.app"] },
  optimism: { id: 10, urls: ["https://mainnet.optimism.io", "https://optimism.drpc.org"] },
  base: { id: 8453, urls: ["https://mainnet.base.org", "https://base-pokt.nodies.app"] },
  polygon: { id: 137, urls: ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"] },
};

export const SUCCESS = "0x442e715f626346e8c54381002da614f62bee8d27386535b2521ec8540898556e";
const SAFE_TX = "0xbb8310d486368db6bd6f849402fdd73ad53d316b5a4b2644ad6efe0f941286d8";
const DOM13 = "0x47e79534a245952e8b16893a336b85a3d9ea9fa8c573f3d803afb92a79469218";
const DOMOLD = "0x035aff83d86937d35b32e04f0ddc6ff469290eef2f1b692d8a815c89404d4749";
const abi = parseAbi(["function execTransaction(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,bytes signatures)"]);

export async function rpc<T>(chain: string, method: string, params: unknown[]): Promise<T> {
  let last: unknown;
  for (const url of RPC[chain].urls) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }), signal: AbortSignal.timeout(15_000), cache: "no-store" });
      const j = await r.json();
      if (j.error) throw new Error(j.error.message);
      return j.result as T;
    } catch (e) { last = e; }
  }
  throw last;
}

export async function findNonce(chain: string, safe: string, tx: string): Promise<{ nonce: number; safeTxHash: string } | { error: string }> {
  if (!RPC[chain]) return { error: "unsupported chain" };
  const t = await rpc<{ to: string; input: Hex; blockNumber: string } | null>(chain, "eth_getTransactionByHash", [tx]);
  const rc = await rpc<{ status: string; logs: { address: string; topics: string[]; data: string }[] } | null>(chain, "eth_getTransactionReceipt", [tx]);
  if (!t || !rc) return { error: "transaction not found" };
  if (t.to?.toLowerCase() !== safe.toLowerCase()) return { error: "the transaction is not a direct call to this Safe" };
  let args;
  try { args = decodeFunctionData({ abi, data: t.input }).args; } catch { return { error: "not an execTransaction call" }; }
  const hashes = rc.logs.filter((l) => l.address.toLowerCase() === safe.toLowerCase() && l.topics[0] === SUCCESS)
    .map((l) => (l.topics.length >= 2 ? l.topics[1] : "0x" + l.data.slice(2, 66)).toLowerCase());
  if (hashes.length === 0) return { error: "no ExecutionSuccess from this Safe" };
  const [to, value, data, op, stg, bg, gp, gt, rr] = args;
  const dom = [
    keccak256(encodeAbiParameters([{ type: "bytes32" }, { type: "uint256" }, { type: "address" }], [DOM13, BigInt(RPC[chain].id), safe as Hex])),
    keccak256(encodeAbiParameters([{ type: "bytes32" }, { type: "address" }], [DOMOLD, safe as Hex])),
  ];
  const hashFor = (n: bigint) => {
    const s = keccak256(encodeAbiParameters(
      [{ type: "bytes32" }, { type: "address" }, { type: "uint256" }, { type: "bytes32" }, { type: "uint8" }, { type: "uint256" }, { type: "uint256" }, { type: "uint256" }, { type: "address" }, { type: "address" }, { type: "uint256" }],
      [SAFE_TX, to, value, keccak256(data), op, stg, bg, gp, gt, rr, n]));
    return dom.map((d) => keccak256(("0x1901" + d.slice(2) + s.slice(2)) as Hex).toLowerCase());
  };
  let top = 0n;
  try {
    const r = await rpc<string>(chain, "eth_call", [{ to: safe, data: "0xaffed0e0" }, t.blockNumber]);
    top = BigInt(r);
  } catch {
    const r = await rpc<string>(chain, "eth_call", [{ to: safe, data: "0xaffed0e0" }, "latest"]);
    top = BigInt(r);
  }
  for (let n = top; n >= 0n && top - n < 20000n; n--) {
    const hs = hashFor(n);
    const hit = hs.find((h) => hashes.includes(h));
    if (hit) return { nonce: Number(n), safeTxHash: hit };
  }
  return { error: "no nonce reproduces the Safe transaction hash" };
}
