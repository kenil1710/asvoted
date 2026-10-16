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
const WHY = {
  "0xbcdb6b99ab2f256f74ccfed3ad361e58eeccff31289ac8b347c4e1d38876905f": "CIP-48's 4M COW to the same Treasury counts too (round-4 rule)",
  "0xf4631cc0ed16c718bd508f374b0064c7db0c36f72dc44a5dd46d73fb3f423b16": "the payment's line also says \"not\" (\"not enough COW\", round-4 rule)",
};
const NOTES = {
  "0xbcdb6b99ab2f256f74ccfed3ad361e58eeccff31289ac8b347c4e1d38876905f":
    "CIP-37 sends 6,000,000 COW to the Treasury Safe, the one amount on its line, and under CIP-37 alone the transfer is AUTHORIZED. Since round 4, a payment also counts with every other filing of the DAO that paid the same payee, under any proposal: CIP-48's 4,000,000 COW to the same Treasury (check #1) makes 10,000,000 COW against CIP-37's 6,000,000. The two rulings differ, so code cannot tell which proposal paid what, and the result is UNCLEAR. This rule is what stops a DAO from escaping a cap by switching proposals (r4_05). It was AS_VOTED on 7a74665.",
  "0xf4631cc0ed16c718bd508f374b0064c7db0c36f72dc44a5dd46d73fb3f423b16":
    "CIP-48's line naming the Treasury Safe states the 4M COW transfer, but the same line goes on: \"In case it happens that there is not enough COW to cover the needs of the solver rewards program, a new CIP should be put in place\". Since round 4, a status or negation word anywhere in the payment's line or bullet subtree (\"rejected\", \"withdrawn\", \"cancelled\", \"not\", \"void\") leaves no cap, because code cannot tell what it negates. It was AS_VOTED on 7a74665.",
  "0x408905df9a2dad947be86dd4ae7b3eca6d90b0247aaef1d632c04a01e13c5fa1":
    "A four-call batch. Two calls (claim and delegate SAFE) are quoted calldata-for-calldata in CIP-16 and are authorized by code. The other two call 0xc0fde70a65c7569fe919be57492228dee8cdb585, a SAFE-token contract that CIP-16 never names. Searched: all 90 proposals of the cow.eth Snapshot space that the hub returns (created 2022-03-01 to 2026-09-30, every state), in title, body, discussion link and choices, case-insensitive, for the full address (and in the body for its first and last 8 hex digits). None names it (`tools/scan_space_mentions.mjs`, output in `docs/research/space_mentions.txt`, run 2026-10-16). This is an address search only; a proposal that described the contract without writing its address would not be found. In the site's words: the execution includes an action proposal CIP-16 does not cover. The DAO can appeal with the proposal that covers it.",
  "0x59a5c685bb44798f287fda67b3df30ddb310dd234e3876a6e4d80298b16547b1":
    "Eight months after SEP #22 the SafeDAO Safe called 0xc0fd…b585 (a module SEP #22 names and discusses) passing 0x03916d54cd6287325b6cf6a9a02a12f79676266c as an argument. Searched: all 56 proposals of the safe.eth Snapshot space that the hub returns (created 2022-10-17 to 2026-09-23, every state), in title, body, discussion link and choices, case-insensitive, for the full address (and in the body for its first and last 8 hex digits). None names it, SEP #22 included (`tools/scan_space_mentions.mjs`, output in `docs/research/space_mentions.txt`, run 2026-10-16). This is an address search only; a proposal that described the argument without writing the address would not be found. In the site's words: the execution includes an action proposal SEP #22 does not cover. The DAO can appeal with the proposal that covers it.",
  "0x1fd579d7bbb8e7e8b8a6e2816f679ca55dddf36728615420d5a7f21c87d4870f":
    "CIP-19 names the treasury Safe that received COW, GNO and ETH but states no amount for it, so the transfers cannot be compared with anything.",
  "0x8a6a840af3c35e320106b4d44b6144d16e17c95b3aaabe6eb2a5c5ddaee08908":
    "PIP-43 sets pay as \"$500 per Trooper per epoch\" in a PSP / ARB split. The Safe sent 343,828 PSP. Comparing dollars with PSP needs a price, which the contract never fetches.",
  "0x2d3d227cc11bb047e4b221e2a1d1c6077ce3534b798659258b08a05e28c9baba":
    "CIP-28 is a standing mandate: send idle (W)ETH from the solver rewards Safe to the treasury Safe monthly. Its lines naming the treasury state no amount; its figures (\"Send 213 ETH and 237 WETH\") are an example on another line. Under the round-3 rule a cap must be the single amount on the recipient's own line, list item or table row, so the 67.0123 WETH cannot be compared with anything. It was AS_VOTED on 93d5be9 against the 237 WETH figure.",
  "0xc2e1137ce39723ae629f47ba58885a32b043820ef3c716346d3806feb2bfe19b":
    "MIP79 sends half of the acqui-hire tokens to the Credit Guild multisig. The line naming the multisig says \"half\" and states no figure; the 175,969 MORPHO total is on another line. Under the round-3 rule that is no cap, so the 87,984.5 MORPHO transfer is UNCLEAR. It was AS_VOTED on 93d5be9 against the total.",
  "0x06a19d459f77e109287002cd3b702fb432b9ee6f1a20607f623faf2aea65d846":
    "Krause House votes with weighted voting, whose result the contract does not compute, so it cannot say the proposal passed. (Its one transfer is also UNCLEAR now: the wallet's own line states no amount.)",
};

const BEFORE = Object.fromEntries(JSON.parse(readFileSync(root + "docs/superseded/7a74665/seed-canonical.json", "utf8")).checks.map((c) => [c.tx, c.final || c.ruling]));
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
  `Registry [\`${dep.AsVotedRegistry.address}\`](${GL}/address/${dep.AsVotedRegistry.address}) (CANONICAL, 6 h contest window), deployed from commit \`${dep.AsVotedRegistry.commit.slice(0, 10)}\`. Every row below is read back from the chain by \`tools/seeds_md.mjs\`; nothing in this table is typed by hand except the explanations, each checked by hand against the execution on its block explorer and the pinned proposal text.`, "",
  `**${rows.length} checks: ${n("AS_VOTED")} AS_VOTED, ${n("DEVIATES")} DEVIATES, ${n("UNCLEAR")} UNCLEAR.** DAOs: ${[...new Set(rows.map((r) => r.space))].join(", ")}. Chains: ${[...new Set(rows.map((r) => r.chain))].join(", ")}.`, "",
  "How they were chosen: every Snapshot space whose settings list a Safe as a treasury on Ethereum, Arbitrum, Optimism, Base or Polygon (`tools/scan_known.mjs`), their executed Safe transactions (Safe Transaction Service, used only to find candidates), and for each the most recent passed proposal of the space that ended before it and names an address it touches (`tools/match.mjs`). Pairs where a different proposal was the right one were corrected by hand (the 67 WETH transfer is CIP-28, not CIP-43). No verdict was chosen; each row is what the contracts ruled.", "",
  "| # | DAO | Chain | Execution | Actions | Proposal (ended) | Ruling | Status |", "|---|---|---|---|---|---|---|---|",
  ...rows.map((r) => `| [${r.check_id}](${SITE}/check/${r.check_id}) | ${r.space} | ${r.chain} | [\`${r.tx.slice(0, 10)}…\`](${EXPL[r.chain]}/tx/${r.tx}) ${r.exec_date} | ${r.actions} | [${r.proposal.replace(/\|/g, "/").slice(0, 70)}](https://ipfs.snapshot.box/ipfs/${r.cid}) (${r.proposal_end}) | **${(r.final || r.ruling).replace("_", " ")}** | ${r.status.toLowerCase()} |`),
  "", "## Before and after round 4", "",
  "Before: the canonical run on `7a74665` (`docs/superseded/7a74665/seed-canonical.json`). After: this run. Every change is explained below.", "",
  "| # | Execution | Proposal | Before | After | Why it changed |", "|---|---|---|---|---|---|",
  ...rows.map((r) => { const b = BEFORE[r.tx] ?? "—"; const a = (r.final || r.ruling); return `| ${r.check_id} | \`${r.tx.slice(0, 10)}…\` | ${r.proposal.replace(/\|/g, "/").slice(0, 50)} | ${b.replace("_", " ")} | ${a.replace("_", " ")} | ${b === a ? "same" : (WHY[r.tx] ?? "see below")} |`; }),
  "", "## Every DEVIATES and UNCLEAR, explained", "",
  ...rows.filter((r) => (r.final || r.ruling) !== "AS_VOTED").map((r) => `- **#${r.check_id} ${r.space}, ${(r.final || r.ruling).replace("_", " ")}.** ${r.summary} ${NOTES[r.tx] ?? ""}`),
  "", "## Rulings, verbatim", "", "As stored on chain. The site shows a DEVIATES sentence as \"includes an action proposal <id> does not cover\": the check compares with the one proposal the filer named, and the DAO can appeal with another.", "",
  ...rows.map((r) => `- #${r.check_id}: ${r.summary}`), "",
];
writeFileSync(root + "docs/SEEDS.md", md.join("\n"));
console.log(`wrote docs/SEEDS.md: ${rows.length} checks, ${n("AS_VOTED")} AS_VOTED / ${n("DEVIATES")} DEVIATES / ${n("UNCLEAR")} UNCLEAR`);
