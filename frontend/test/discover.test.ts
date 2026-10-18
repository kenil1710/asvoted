/**
 * Proposal discovery: bounded pagination past the newest 25, address / ENS /
 * amount normalization, and unmatched executions recorded visibly.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { encodeFunctionData, encodePacked, getAddress, parseAbi, type Hex } from "viem";
import { type Proposal, type Sources, PAGE, decodeExecution, discover, ensNames, namedAddresses, sameAmount, statedAmounts } from "../src/lib/patrol/discover";
import { runCore } from "../src/lib/patrol/core";
import { emptyState, execKey, safeKey } from "../src/lib/patrol/state";
import { World } from "./mock";

const safeAbi = parseAbi(["function execTransaction(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,bytes signatures)"]);
const erc20 = parseAbi(["function transfer(address to,uint256 amount)"]);
const multi = parseAbi(["function multiSend(bytes transactions)"]);
const Z = "0x0000000000000000000000000000000000000000";
const USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48";
const DAI = "0x6b175474e89094c44da98b954eedeac495271d0f";
const RECIPIENT = "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed";   // EIP-55: 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed
const OTHER = "0x1111111111111111111111111111111111111111";
const exec = (to: string, value: bigint, data: Hex, op = 0) =>
  encodeFunctionData({ abi: safeAbi, functionName: "execTransaction", args: [to as Hex, value, data, op, 0n, 0n, 0n, Z, Z, "0x"] });
const transfer = (to: string, amount: bigint) => encodeFunctionData({ abi: erc20, functionName: "transfer", args: [to as Hex, amount] });

function prop(i: number, body: string, win = true): Proposal {
  return { ipfs: "cid" + i, body, choices: ["For", "Against"], scores: win ? [10, 1] : [1, 10], scores_state: "final", end: 1_000_000 - i };
}
function sources(rows: Proposal[], extra: Partial<Sources> = {}) {
  const calls: number[] = [];
  const src: Sources = {
    page: async (_s, _b, skip, first) => { calls.push(skip); return rows.slice(skip, skip + first); },
    resolveEns: async (n) => ({ "grants.acme.eth": RECIPIENT } as Record<string, string>)[n] ?? null,
    token: async (a) => ({ [USDC]: { symbol: "USDC", decimals: 6 }, [DAI]: { symbol: "DAI", decimals: 18 } } as Record<string, { symbol: string; decimals: number }>)[a] ?? null,
    native: "ETH",
    ...extra,
  };
  return { src, calls };
}

test("decodes a MultiSend batch into each call and transfer", () => {
  const inner = [
    encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, USDC, 0n, 68n, transfer(RECIPIENT, 50_000n * 10n ** 6n)]),
    encodePacked(["uint8", "address", "uint256", "uint256", "bytes"], [0, OTHER, 10n ** 18n, 0n, "0x"]),
  ];
  const data = encodeFunctionData({ abi: multi, functionName: "multiSend", args: [("0x" + inner.map((x) => x.slice(2)).join("")) as Hex] });
  const d = decodeExecution(exec("0x40a2accbd92bca938b02010e17a5b8929b49130d", 0n, data, 1));
  assert.equal(d.calls.length, 2);
  assert.deepEqual(d.transfers, [{ token: USDC, to: RECIPIENT, amount: 50_000n * 10n ** 6n }, { token: "", to: OTHER, amount: 10n ** 18n }]);
  assert.ok(d.touched.has(RECIPIENT) && d.touched.has(OTHER) && d.touched.has(USDC));
});

test("pagination: a match beyond the newest 25 (and beyond the first page) is found", async () => {
  const rows = Array.from({ length: 260 }, (_, i) => prop(i, i === 140 ? `Pay ${RECIPIENT} 100 USDC` : "unrelated"));
  const { src, calls } = sources(rows);
  const r = await discover(src, "acme.eth", 2_000_000, decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 100n * 10n ** 6n))));
  assert.ok("cid" in r && r.cid === "cid140", JSON.stringify(r));
  assert.deepEqual(calls, [0, 100, 200]);   // stopped at the short last page
  assert.equal(r.read, 260);
});

test("pagination is bounded: at most maxPages pages are read, and the report says how many", async () => {
  const rows = Array.from({ length: 5000 }, (_, i) => prop(i, "unrelated"));
  const { src, calls } = sources(rows);
  const r = await discover(src, "acme.eth", 2_000_000, decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 1n))), 4);
  assert.equal(calls.length, 4);
  assert.ok("error" in r && r.read === 4 * PAGE && r.pages === 4);
});

test("normalization: a checksummed address in the text matches the lowercase execution; a bad checksum is ignored", async () => {
  const cs = getAddress(RECIPIENT);
  assert.notEqual(cs, RECIPIENT);
  assert.deepEqual([...namedAddresses(`to ${cs}`).addresses], [RECIPIENT]);
  assert.deepEqual([...namedAddresses(`to ${RECIPIENT.toUpperCase().replace("0X", "0x")}`).addresses], [RECIPIENT]);
  const i = cs.search(/[a-fA-F]/);   // flip the case of one letter: still mixed case, wrong checksum
  const bad = cs.slice(0, i) + (cs[i] === cs[i].toLowerCase() ? cs[i].toUpperCase() : cs[i].toLowerCase()) + cs.slice(i + 1);
  const nb = namedAddresses(`to ${bad}`);
  assert.deepEqual([nb.addresses.size, nb.badChecksum], [0, [bad]]);
  const ex = decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 5n)));
  const ok = await discover(sources([prop(1, `Send 5 USDC to ${cs}`)]).src, "acme.eth", 2e6, ex);
  assert.ok("cid" in ok);
  const no = await discover(sources([prop(1, `Send 5 USDC to ${bad}`)]).src, "acme.eth", 2e6, ex);
  assert.ok("error" in no && /bad checksum/.test(no.error), JSON.stringify(no));
});

test("ENS names are normalized and resolved", async () => {
  assert.deepEqual(ensNames("Send it to Grants.ACME.eth, then to x.eth."), ["grants.acme.eth", "x.eth"]);
  const ex = decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 5n)));
  const r = await discover(sources([prop(1, "Send 5 USDC to Grants.Acme.eth")]).src, "acme.eth", 2e6, ex);
  assert.ok("cid" in r && /ENS name grants\.acme\.eth/.test(r.why), JSON.stringify(r));
  const u = await discover(sources([prop(1, "Send 5 USDC to nobody.eth")]).src, "acme.eth", 2e6, ex);
  assert.ok("error" in u);
});

test("amounts are compared in the token's decimals; a proposal stating the moved amount is preferred over a newer one", async () => {
  assert.deepEqual(statedAmounts("pay 50,000 USDC and 1.5 ETH and 12k DAI"), [
    { symbol: "USDC", units: 50000n, scale: 0 }, { symbol: "ETH", units: 15n, scale: 1 }, { symbol: "DAI", units: 12000n, scale: 0 }]);
  assert.ok(sameAmount({ symbol: "USDC", units: 50000n, scale: 0 }, 50_000n * 10n ** 6n, 6));
  assert.ok(sameAmount({ symbol: "ETH", units: 15n, scale: 1 }, 15n * 10n ** 17n, 18));
  assert.ok(!sameAmount({ symbol: "USDC", units: 50000n, scale: 0 }, 50_001n * 10n ** 6n, 6));
  assert.ok(sameAmount({ symbol: "ETH", units: 123n, scale: 2 }, 12345n * 10n ** 14n, 18));   // stated to 2 decimals
  const ex = decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 50_000n * 10n ** 6n)));
  const rows = [prop(1, `Send 40,000 USDC to ${RECIPIENT}`), prop(2, `Send 50,000 USDC to ${RECIPIENT}`)];
  const r = await discover(sources(rows).src, "acme.eth", 2e6, ex);
  assert.ok("cid" in r && r.cid === "cid2" && /stating an amount/.test(r.why), JSON.stringify(r));
});

test("failed proposals are never candidates", async () => {
  const ex = decodeExecution(exec(USDC, 0n, transfer(RECIPIENT, 5n)));
  const r = await discover(sources([prop(1, `Send 5 USDC to ${RECIPIENT}`, false)]).src, "acme.eth", 2e6, ex);
  assert.ok("error" in r && r.passed === 0);
});

test("an unmatched execution is recorded in the state file with its reason, and the checkpoint moves on", async () => {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, 999_990);
  w.unmatched = () => "no passed proposal names an address this execution touches (3 passed of 40 read); not filed";
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: 999_900, origin: 0, updated: "" };
  const rep = await runCore(w.deps(), s, { maxWrites: 10, timeBudgetMs: 1e9, maxSpan: { ethereum: 1000 }, logChunk: 1000, initialBackfill: {} });
  assert.equal(rep.unmatched, 1);
  assert.deepEqual([s.unmatched[0].tx, s.unmatched[0].space, s.unmatched[0].safe_tx_hash], [lg.tx, d.space, lg.safeTxHash]);
  assert.match(s.unmatched[0].reason, /3 passed of 40 read/);
  assert.equal(s.processed[execKey(d.chain, d.safe, lg.safeTxHash)].status, "unmatched");
  assert.equal(s.checkpoints[safeKey(d.chain, d.safe)].block, 1_000_000);
});
