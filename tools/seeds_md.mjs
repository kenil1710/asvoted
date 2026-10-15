/**
 * docs/SEEDS.md and docs/seed-canonical.json from CANONICAL registry state:
 * every check, its execution and proposal records, read back from the chain.
 * Hand-verified explanations for every DEVIATES / UNCLEAR are in NOTES below.
 *   STUDIO_RPC=... node tools/seeds_md.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(new URL("../test/package.json", import.meta.url));
const { createClient } = require("genlayer-js");
const { studioDevnet } = require("genlayer-js/chains");
const root = new URL("..", import.meta.url).pathname;
const dep = JSON.parse(readFileSync(root + "deployments.json", "utf8")).contracts;
const relay = process.env.STUDIO_RPC;
const chain = relay ? { ...studioDevnet, rpcUrls: { ...studioDevnet.rpcUrls, default: { ...studioDevnet.rpcUrls.default, http: [relay] } } } : studioDevnet;
const client = createClient({ chain });
const plain = (v) => (v instanceof Map ? Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)])) : Array.isArray(v) ? v.map(plain) : typeof v === "bigint" ? Number(v) : v);
async function view(address, fn, args = []) {
  for (let i = 0; i < 6; i++) {
    try { const r = await client.readContract({ address, functionName: fn, args }); return typeof r === "string" ? JSON.parse(r) : plain(r); }
    catch (e) { await new Promise((r) => setTimeout(r, 4000 * (i + 1))); if (i === 5) throw e; }
  }
}
const EXPL = { ethereum: "https://etherscan.io", optimism: "https://optimistic.etherscan.io", base: "https://basescan.org", arbitrum: "https://arbiscan.io", polygon: "https://polygonscan.com" };
const GL = "https://explorer-studio-dev.genlayer.com";
const SITE = "https://asvoted.vercel.app";

// Hand-verified on chain and in the proposal text (tools/live.py pair ...).
const NOTES = {
  "0x408905df9a2dad947be86dd4ae7b3eca6d90b0247aaef1d632c04a01e13c5fa1":
    "A four-call batch. Two calls (claim and delegate SAFE) are quoted calldata-for-calldata in CIP-16 and are authorized by code. The other two call 0xc0fd…b585, a SAFE-token contract that CIP-16 never names (no CoW proposal in the hub mentions it). The proposal does not name an address the execution uses.",
  "0x59a5c685bb44798f287fda67b3df30ddb310dd234e3876a6e4d80298b16547b1":
    "Eight months after SEP #22 the SafeDAO Safe called 0xc0fd…b585 (a module SEP #22 discusses) passing 0x0391…266c as an argument. Neither SEP #22 nor any other SafeDAO proposal in the hub names that address.",
  "0x1fd579d7bbb8e7e8b8a6e2816f679ca55dddf36728615420d5a7f21c87d4870f":
    "CIP-19 names the treasury Safe that received COW, GNO and ETH but states no amount for it, so the transfers cannot be compared with anything.",
  "0x8a6a840af3c35e320106b4d44b6144d16e17c95b3aaabe6eb2a5c5ddaee08908":
    "PIP-43 sets pay as \"$500 per Trooper per epoch\" in a PSP / ARB split. The Safe sent 343,828 PSP. Comparing dollars with PSP needs a price, which the contract never fetches.",
  "0x06a19d459f77e109287002cd3b702fb432b9ee6f1a20607f623faf2aea65d846":
    "The transfer itself is authorized, but Krause House votes with weighted voting, whose result the contract does not compute, so it cannot say the proposal passed.",
};

const st = await view(dep.AsVotedRegistry.address, "get_stats");
const out = [];
for (let off = 0; off < st.checks; off += 25) {
  const page = await view(dep.AsVotedRegistry.address, "get_checks", [off, 25]);
  out.push(...page.checks);
}
out.sort((a, b) => a.check_id - b.check_id);
const rows = [];
for (const c of out) {
  const ex = await view(dep.ExecReader.address, "get_execution", [c.exec_id]);
  const vote = await view(dep.VoteReader.address, "get_proposal", [c.vote_id]);
  const dao = await view(dep.AsVotedRegistry.address, "get_dao", [c.dao_id]);
  rows.push({ check_id: c.check_id, space: dao.space, chain: c.chain, safe: c.safe, tx: c.tx, block: c.block, exec_date: new Date(ex.block_time * 1000).toISOString().slice(0, 10),
    actions: ex.n_actions, proposal: vote.title, cid: c.cid, proposal_end: new Date(vote.end * 1000).toISOString().slice(0, 10), vote_type: vote.type, vote_outcome: vote.outcome,
    status: c.status, ruling: c.ruling, final: c.final_verdict, summary: c.ruling_summary, filer: c.filer, note: c.note, exec_id: c.exec_id, vote_id: c.vote_id });
}
const n = (v) => rows.filter((r) => (r.final || r.ruling) === v).length;
writeFileSync(root + "docs/seed-canonical.json", JSON.stringify({ registry: dep.AsVotedRegistry.address, commit: dep.AsVotedRegistry.commit, read_at: new Date().toISOString(), stats: st, checks: rows }, null, 2) + "\n");
const md = [
  "# Seeds: real DAO executions on the canonical registry", "",
  `Registry [\`${dep.AsVotedRegistry.address}\`](${GL}/address/${dep.AsVotedRegistry.address}) (CANONICAL, 1 h contest window), deployed from commit \`${dep.AsVotedRegistry.commit.slice(0, 10)}\`. Every row below is read back from the chain by \`tools/seeds_md.mjs\`; nothing in this table is typed by hand except the explanations, each checked by hand against the execution on its block explorer and the pinned proposal text.`, "",
  `**${rows.length} checks: ${n("AS_VOTED")} AS_VOTED, ${n("DEVIATES")} DEVIATES, ${n("UNCLEAR")} UNCLEAR.** DAOs: ${[...new Set(rows.map((r) => r.space))].join(", ")}. Chains: ${[...new Set(rows.map((r) => r.chain))].join(", ")}.`, "",
  "How they were chosen: every Snapshot space whose settings list a Safe as a treasury on Ethereum, Arbitrum, Optimism, Base or Polygon (`tools/scan_known.mjs`), their executed Safe transactions (Safe Transaction Service, used only to find candidates), and for each the most recent passed proposal of the space that ended before it and names an address it touches (`tools/match.mjs`). Pairs where a different proposal was the right one were corrected by hand (the 67 WETH transfer is CIP-28, not CIP-43). No verdict was chosen; each row is what the contracts ruled.", "",
  "| # | DAO | Chain | Execution | Actions | Proposal (ended) | Ruling | Status |", "|---|---|---|---|---|---|---|---|",
  ...rows.map((r) => `| [${r.check_id}](${SITE}/check/${r.check_id}) | ${r.space} | ${r.chain} | [\`${r.tx.slice(0, 10)}…\`](${EXPL[r.chain]}/tx/${r.tx}) ${r.exec_date} | ${r.actions} | [${r.proposal.replace(/\|/g, "/").slice(0, 70)}](https://ipfs.snapshot.box/ipfs/${r.cid}) (${r.proposal_end}) | **${(r.final || r.ruling).replace("_", " ")}** | ${r.status.toLowerCase()} |`),
  "", "## Every DEVIATES and UNCLEAR, explained", "",
  ...rows.filter((r) => (r.final || r.ruling) !== "AS_VOTED").map((r) => `- **#${r.check_id} ${r.space}, ${(r.final || r.ruling).replace("_", " ")}.** ${r.summary} ${NOTES[r.tx] ?? ""}`),
  "", "## Rulings, verbatim", "",
  ...rows.map((r) => `- #${r.check_id}: ${r.summary}`), "",
];
writeFileSync(root + "docs/SEEDS.md", md.join("\n"));
console.log(`wrote docs/SEEDS.md: ${rows.length} checks, ${n("AS_VOTED")} AS_VOTED / ${n("DEVIATES")} DEVIATES / ${n("UNCLEAR")} UNCLEAR`);
