// Writes docs/SUBMISSION.md with exact character counts.
import { readFileSync, writeFileSync } from "node:fs";
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8")).contracts;
const commit = Object.values(dep)[0].commit;
const one = "AsVoted checks every action a DAO's Safe executed against the passed Snapshot proposal its filer names: decoded calldata, CID-proven text, code-first rulings, pledges, appeals.";
const seeds = JSON.parse(readFileSync(new URL("../docs/seed-canonical.json", import.meta.url), "utf8"));
const rul = (v) => seeds.checks.filter((c) => (c.final || c.ruling) === v).length;
const nFinal = seeds.checks.filter((c) => c.status === "FINAL").length;
const demo = JSON.parse(readFileSync(new URL("../docs/seed-demo.json", import.meta.url), "utf8"));
const dOk = demo.results.filter((r) => r.ok).length;
const tests = ["test_asvoted", "test_attacks", "test_attacks_r2", "test_attacks_r3", "test_attacks_r4"]
  .map((f) => (readFileSync(new URL(`../test/${f}.py`, import.meta.url), "utf8").match(/^    def test_/gm) || []).length).reduce((a, b) => a + b, 0);
const desc = `Most DAOs vote on Snapshot and a Safe multisig executes the result; nothing checks the two match. AsVoted reads the execution from two RPCs that must agree, decodes every action (MultiSend batches included) and verifies the Safe's own success event. It reads the proposal by IPFS CID, hashing it in the contract, checks the hub and the space's treasury list, and computes whether it passed. Code rules on each action: unnamed recipient, amount over the one figure the proposal states for it (summed across transfers), unnamed DELEGATECALL; ambiguity is UNCLEAR. A model only reads calls described in words, and must quote the text. DAOs pledge a bond; anyone files with a stake; one appeal; deadlines; pull payouts; no admin. A patrol bot watches listed Safes. ${seeds.checks.length} real executions: ${rul("AS_VOTED")} as voted, ${rul("DEVIATES")} deviate, ${rul("UNCLEAR")} unclear.`;
const steps = [
  "Open https://asvoted.vercel.app and pick a check: the proposal as voted on the left, every decoded action of the Safe execution on the right, a verdict per action.",
  "Open /verify and click Compare: each contract's code is read from Studio Dev and hashed against the deploy commit on GitHub in your browser.",
  "Switch the header to Demo, connect a wallet funded from the Studio faucet, and file a check on /file with a listed DAO, a Safe tx hash and a proposal CID.",
  "On the check page, judge and apply the ruling, then appeal within 90 seconds (only the DAO, answering a DEVIATES, may name another proposal) or finalize after it.",
  "Run the offline suite (cd test && python3 -m unittest test_asvoted test_attacks test_attacks_r2 test_attacks_r3 test_attacks_r4) and read docs/SEEDS.md and docs/FINAL_CHECK.md.",
];
const verify = `All 9 contracts deployed from commit ${commit.slice(0, 7)}; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: ${seeds.checks.length} real seeds, ${nFinal === seeds.checks.length ? `all ${seeds.checks.length} final` : "all ruled, final after the 6 h contest window"} (${["AS_VOTED", "DEVIATES", "UNCLEAR"].map((v) => `${seeds.checks.filter((c) => (c.final_verdict || c.ruling) === v).length} ${v}`).join(", ")}), each linked to Etherscan and IPFS. Demo registry: every path run on chain, ${dOk}/${demo.results.length}; ${demo.payouts.filter((p) => p.ok).length}/${demo.payouts.length} payouts arrived (recipient eth_getBalance checked); registry eth_getBalance ${demo.registry_balance.after_claims} after the claims. ${tests} offline tests incl. 4 attack rounds.`;
const EX = "https://explorer-studio-dev.genlayer.com/address/";
const ev = [
  ["Repository", "https://github.com/kenil1710/asvoted"], ["Live site", "https://asvoted.vercel.app"],
  ...Object.entries(dep).map(([k, v]) => [`${k} (explorer)`, EX + v.address]),
  ["Seeds", "https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md"], ["Final check", "https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md"],
  ["Attack report", "https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md"], ["Attack report, round 4", "https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT_R4.md"], ["Demo video", "https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4"],
  ["Vertical cut", "https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4"], ["Medium article (draft)", "https://github.com/kenil1710/asvoted/blob/main/docs/medium.md"],
];
const n = (s) => [...s].length;
const out = ["# Submission", "", `## One-liner (${n(one)}/180)`, "", one, "", `## Description (${n(desc)}/1000)`, "", desc, "", "## How to try it (5 steps)", "",
  ...steps.map((s, i) => `${i + 1}. ${s} (${n(s)} chars)`), "", `## Review verification (${n(verify)}/500)`, "", verify, "", "## Evidence", "",
  ...ev.flatMap(([k, v]) => [`- ${k}: ${v}`, ...(k === "Demo video" || k === "Vertical cut" ? ["  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged."] : [])]), ""];
if (n(one) > 180 || n(desc) > 1000 || n(verify) > 500) throw new Error(`too long: ${n(one)} ${n(desc)} ${n(verify)}`);
writeFileSync(new URL("../docs/SUBMISSION.md", import.meta.url), out.join("\n"));
console.log(`one-liner ${n(one)}, description ${n(desc)}, verification ${n(verify)}`);
