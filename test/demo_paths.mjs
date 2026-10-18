/**
 * Every path, end to end, on the DEMO registry (90 s contest windows, 600 s
 * judge / appeal deadlines), with real executions and proposals:
 *
 *   refusals   list_dao of a Safe the space does not list; claim_dao by a
 *              non-admin; duplicate filing; payable call with a wrong amount
 *   AS_VOTED   CoW CIP-30 (oSnap)                        -> finalize, stake to pledge
 *   DEVIATES   CoW CIP-16 batch                          -> finalize, pledge slashed, bounty
 *   appeal won CoW 6,000,000 COW to the Treasury (CIP-37) filed against CIP-30 (wrong: oSnap)
 *              -> DAO appeals naming CIP-37 -> AS_VOTED
 *   appeal lost CoW Treasury CIP-69 signMessage call     -> DAO appeals with words only -> DEVIATES stands
 *   UNCLEAR    CoW CIP-19                                -> final at once, refund
 *   expiry     CoW CIP-37 never judged                   -> expire after 600 s -> UNCLEAR
 *   appeal expiry  CoW CIP-29 AS_VOTED appealed, never judged -> expire -> ruling stands, bond back
 *   consumer   DaoStandingDemo states through GrantGateDemo, which acts only on COMPLIANT:
 *              NO_COVERAGE   CoW Treasury listing with nothing verified yet
 *              PENDING       ParaSwap PIP-59 (40.203 WETH returned to Bybit) filed, not final
 *              COMPLIANT     PIP-59 FINAL AS_VOTED, and the patrol has scanned the ParaSwap Safe
 *                            and recorded its coverage heartbeat (frontend/scripts/patrol-run.ts)
 *              DEVIATES      CoW Treasury's 200,000 BAL transfer of 2026-10-15, filed against
 *                            CIP-69, which does not name the recipient, FINAL
 *              STALE_MONITORING  the ParaSwap heartbeat older than the demo's 1 h limit
 *   drain      controller withdraws the pledge, everyone claims; each claim must
 *              finalize with an external transfer that lands on the claimer
 *              (eth_getBalance before/after), and the registry's own
 *              eth_getBalance must reach 0
 *
 *   node demo_paths.mjs [--from=step]
 * Writes docs/demo-run.log (stdout) and docs/seed-demo.json.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { connect, accounts, argOf, returnedJson, sleep } from "./harness.mjs";
import { balanceOf, provenClaim } from "../tools/payouts.mjs";

const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8")).contracts;
const A = { er: dep.ExecReader.address, vr: dep.VoteReader.address, jg: dep.AsVotedJudge.address, rg: dep.AsVotedRegistryDemo.address, gate: dep.GrantGateDemo.address };
const acc = accounts();
const who = (role) => acc[role].address.toLowerCase();
const C = {};
for (const role of ["filer", "filer2", "dao", "appellant", "demo"]) {
  C[role] = { er: connect({ address: A.er, role }), vr: connect({ address: A.vr, role }), jg: connect({ address: A.jg, role }), rg: connect({ address: A.rg, role }), gate: connect({ address: A.gate, role }) };
}
const J = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const STAKE = 10n ** 17n, BOND = 10n ** 17n, GEN = 10n ** 18n;
const COW = "0xcA771eda0c70aA7d053aB1B25004559B918FE662", TREAS = "0x616dE58c011F8736fa20c7Ae5352F7f6FB9F0669";
const PARA = "0x619BBf92Fd6bA59893327676B2685A3762a49a33";
const PATROL = who("patrol");
const CID = {
  cip48: "bafkreigatik76cmd2amxbkav55jzrexyygnebausjg7isbb2akbnevw4xq", cip16: "bafkreie2je5vvgzlv34gwpllxzr5pkcuzi5ujy4tujhdddpzy66ka7nuv4",
  cip43: "bafkreigqmaollb3qnv7tjrrqp2huwnds6dyxeh33lybvovdpowza6ms6sq", cip28: "bafkreie2zitrxqwtmz6ehbompehqnhy2duddhhp4z2udmw645dcbpt3i4m",
  cip69: "bafkreid7zgwhd7la7rxam7d4yltudm4snzbpjimzqa5n4l7bek26hll7pe", cip19: "bafkreigeksmh3n7sxmon5y7vhow2vieuxoyhyq3u42ent6cbwq7sfenwpq",
  cip37: "bafkreif6v7upfwppmyklokvzihh67cbb7a2inprdp6t7sytgas5za5iaam", cip24: "bafkreidsqpnzeomzl5kyaashogdq3mztw7yhkoim35ndc7xysmuflq4xcm", cip30: "bafkreie7k2pbalnxl6hsupdmhd4i76tuc2vm52gwijqxatyzvo6yxf2m6q", cip29: "bafkreif2pkxscvnyvvnb2v2l2fftc54cysnbxdvoaousbuedsl2mgi6qqu",
  pip59: "bafkreiand2nimf36noh3zzlsi7gw7bpijbz5g3fleqf6pty6krfyoixsum",
};
const TX = {
  cip48: ["0xf4631cc0ed16c718bd508f374b0064c7db0c36f72dc44a5dd46d73fb3f423b16", 27, COW], cip16: ["0x408905df9a2dad947be86dd4ae7b3eca6d90b0247aaef1d632c04a01e13c5fa1", 19, COW],
  weth67: ["0x2d3d227cc11bb047e4b221e2a1d1c6077ce3534b798659258b08a05e28c9baba", 26, COW], cip69: ["0x5b453427e61374b5d023a9920943fcbe05a54b7d06b9fc557d512c20351abe22", 891, TREAS],
  bal200k: ["0xa85e7333380b8d40be2fa89c24cb7183be0006d1c2e78134ada10ced08336ad3", 902, TREAS],
  cip19: ["0x1fd579d7bbb8e7e8b8a6e2816f679ca55dddf36728615420d5a7f21c87d4870f", 9, COW], cip37: ["0xbcdb6b99ab2f256f74ccfed3ad361e58eeccff31289ac8b347c4e1d38876905f", 22, COW],
  cip29: ["0xaa412db50fb9cb384d56ddec01a00997d686927d332f13ddf93e7644a5f47c29", 17, COW],
  cip24: ["0x1af684f90ded18dcd55438f8c1acc64c427c8aa2cfa223d56a6d043d7f8e67f7", 13, COW],
  cip30: ["0x6b5e48e34bedc27312c5d3fb726d0764af95e62ff23b49e0c3d16f069bbccbaa", 18, COW],
  pip59: ["0xb35fba262820083d4c3e262e95d9c2b2458452350409946bd9a67948afe986f6", 88, PARA, "paraswap-dao.eth"],
};
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const results = [];
const expect = (name, ok, detail) => { results.push({ name, ok, detail }); log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`); };
const now = () => Math.floor(Date.now() / 1000);

async function w(role, c, fn, args, value = 0n) {
  log(`→ ${role} ${fn} ${JSON.stringify(args).slice(0, 110)}${value ? " +" + value : ""}`);
  const out = await C[role][c].send(fn, args, value);
  const r = returnedJson(out);
  log(`  ${out.ok ? "OK" : "REVERTED"} ${out.status} ${out.seconds?.toFixed(0)}s ${out.hash} ${out.ok ? JSON.stringify(r ?? out.returned ?? "").slice(0, 200) : (out.revertReason ?? "").slice(0, 160)}`);
  return { ...out, r };
}
const v = async (c, fn, args = []) => J(await C.filer[c].view(fn, args));

async function freshSpace(space, chain, safe) {
  const bid = Number(await v("vr", "get_binding_id", [space, chain, safe]));
  const b = bid ? await v("vr", "get_binding", [bid]) : null;
  if (!b || now() - b.read_at > 3000) await w("filer", "vr", "read_space", [space, chain, safe]);
}
async function freshVote(cid, safe) {
  let id = Number(await v("vr", "get_proposal_id", [cid, "ethereum", safe]));
  const p = id ? await v("vr", "get_proposal", [id]) : null;
  if (!p || now() - p.read_at > 3000) {
    // an IPFS gateway or the hub failing inside GenVM is refused (RPC_UNREADABLE), never guessed: retry it
    for (let i = 0; i < 4; i++) {
      const out = await w("filer", "vr", "read_proposal", [cid, "ethereum", safe]);
      if (out.ok || !/RPC_UNREADABLE/.test(out.revertReason ?? "")) break;
      log(`  proposal unreadable (attempt ${i + 1}), retrying in 30s`);
      await sleep(30_000);
    }
    id = Number(await v("vr", "get_proposal_id", [cid, "ethereum", safe]));
  }
  return id;
}
/** The proposal's ENS names resolved at the execution's L1 block, which a filing needs. */
async function namesAt(vid, eid) {
  const p = await v("vr", "get_proposal", [vid]);
  const e = await v("er", "get_execution", [eid]);
  if (!p.ens_names?.length || !e.l1_block) return;
  const have = await v("vr", "get_names_at", [vid, e.l1_block]);
  if (!have.found) await w("filer", "vr", "read_names_at", [vid, e.l1_block]);
}
async function execId(key) {
  const [tx, nonce, safe] = TX[key];
  let id = Number(await v("er", "get_execution_id", ["ethereum", safe, tx]));
  if (!id) { await w("filer", "er", "read_execution", ["ethereum", safe, tx, nonce]); id = Number(await v("er", "get_execution_id", ["ethereum", safe, tx])); }
  return id;
}
async function daoFor(safe, space = "cow.eth") {
  let id = Number(await v("rg", "get_dao_id", [space, "ethereum", safe]));
  if (!id) { await freshSpace(space, "ethereum", safe); await w("filer", "rg", "list_dao", [space, "ethereum", safe]); id = Number(await v("rg", "get_dao_id", [space, "ethereum", safe])); }
  return id;
}
/** GrantGateDemo's answer for a DAO now: the request it logged, with DaoStandingDemo's state. */
async function grant(dao, purpose) {
  await w("demo", "gate", "request_grant", [dao, purpose]);
  const last = J(await C.demo.gate.view("get_requests", [0, 1])).requests[0];
  return last ?? {};
}
async function file(role, key, cidKey, note) {
  const [tx, , safe, space] = TX[key];
  const existing = Number(await v("rg", "get_check_id_by_tx", ["ethereum", safe, tx]));
  if (existing) {
    // a check that expired unjudged (a stalled run) proved nothing: refile it,
    // except the path that is about expiry itself
    const ec = await v("rg", "get_check", [existing]);
    if (!(ec.status === "FINAL" && ec.final_how === "EXPIRED_UNJUDGED" && key !== "cip24")) return existing;
    log(`  check #${existing} expired unjudged; refiling ${key}`);
  }
  const dao = await daoFor(safe, space);
  const e = await execId(key);
  const vid = await freshVote(CID[cidKey], safe);
  await namesAt(vid, e);
  const out = await w(role, "rg", "file_check", [dao, e, vid, note], STAKE);
  if (out.r?.ok === false) log("  refused:", out.r.reason);
  return Number(await v("rg", "get_check_id_by_tx", ["ethereum", safe, tx]));
}
async function judgeRule(role, id) {
  const c = await v("rg", "get_check", [id]);
  const j = await v("jg", "get_judgment", [A.rg, id, c.round]);
  for (let i = 0; i < 3 && !j.found; i++) {
    const out = await w(role, "jg", "judge", [A.rg, id]);
    if (out.ok) break;
  }
  await w(role, "rg", "rule", [id]);
  return v("rg", "get_check", [id]);
}
async function waitPast(t, label) {
  const s = t - now() + 5;
  if (s > 0) { log(`… waiting ${s}s for ${label}`); await sleep(s * 1000); }
}

const D = {};
// --- refusals and claim
const cow = await daoFor(COW);
const treas = await daoFor(TREAS);
const para = await daoFor(PARA, "paraswap-dao.eth");
const randomSafe = "0x00000000000000000000000000000000000000a5";
await freshSpace("cow.eth", "ethereum", randomSafe);
{
  const out = await w("filer", "rg", "list_dao", ["cow.eth", "ethereum", randomSafe]);
  expect("listing a Safe the space does not list is refused", !out.ok && /SAFE_NOT_LISTED/.test(out.revertReason ?? ""), out.revertReason);
}
await freshSpace("cow.eth", "ethereum", COW);
{
  const out = await w("filer", "rg", "claim_dao", [cow]);
  expect("claim by a non-admin is refused", !out.ok && /NOT_AN_ADMIN/.test(out.revertReason ?? ""), out.revertReason);
}
for (const id of [cow, treas, para]) {
  const d = await v("rg", "get_dao", [id]);
  if (d.controller !== who("dao")) await w("dao", "rg", "claim_dao", [id]);
}
expect("demo controller claims both listings", (await v("rg", "get_dao", [cow])).controller === who("dao") && (await v("rg", "get_dao", [treas])).controller === who("dao"));
if (BigInt((await v("rg", "get_dao", [cow])).pledge) === 0n) await w("dao", "rg", "pledge", [cow], 5n * GEN);
if (BigInt((await v("rg", "get_dao", [treas])).pledge) === 0n) await w("dao", "rg", "pledge", [treas], 2n * GEN);
{
  const out = await w("filer", "rg", "pledge", [cow], GEN);
  expect("pledge by a non-controller is credited back, ok:false", out.ok && out.r?.ok === false, out.r?.reason);
}
{
  const g = await grant(treas, "release tranche 1");
  expect("GrantGate refuses a DAO with nothing verified: NO_COVERAGE, never a favourable default", g.carried_out === false && g.state === "NO_COVERAGE", JSON.stringify(g));
}

// the proposal the winning appeal names, read before filing so judging starts inside every 600 s judge window
const right = await freshVote(CID.cip37, COW);
await namesAt(right, await execId("cip37"));

// --- file everything
D.asv = await file("filer", "cip30", "cip30", "demo: as voted");
D.dev = await file("filer", "cip16", "cip16", "demo: deviates");
D.won = await file("filer2", "cip37", "cip30", "demo: filed against the wrong proposal");
D.lost = await file("filer2", "cip69", "cip69", "demo: appeal lost");
D.unc = await file("filer", "weth67", "cip28", "demo: unclear");
D.exp = await file("filer", "cip24", "cip24", "demo: never judged, expires");
D.aexp = await file("filer2", "cip29", "cip29", "demo: appeal never judged");
D.gate = await file("filer", "bal200k", "cip69", "demo: a recent execution against a proposal that does not cover it, for GrantGate");
D.para = await file("filer", "pip59", "pip59", "demo: as voted, for DaoStanding COMPLIANT");
log("checks", JSON.stringify(D));
{
  const g = await grant(para, "release tranche 1");
  expect("GrantGate refuses while the DAO's check is open: PENDING", g.carried_out === false && g.state === "PENDING", JSON.stringify(g));
}
{
  const [tx, , safe] = TX.cip30;
  const e = Number(await v("er", "get_execution_id", ["ethereum", safe, tx]));
  const vid = await freshVote(CID.cip30, safe);
  const out = await w("appellant", "rg", "file_check", [cow, e, vid, "duplicate"], STAKE);
  expect("duplicate filing is refused (stake credited back)", out.r?.ok === false && /DUPLICATE/.test(out.r?.reason ?? ""), out.r?.reason);
  const bad = await w("appellant", "rg", "file_check", [cow, e, vid, "wrong stake"], STAKE + 1n);
  expect("wrong stake is refused (credited back)", bad.r?.ok === false && /STAKE_MUST_BE/.test(bad.r?.reason ?? ""), bad.r?.reason);
}

// --- judge and rule; an appeal goes in right after its ruling (90 s window)
const APPEAL = {
  won: ["dao", "This transfer of 6,000,000 COW to the Treasury Safe implements CIP-37, COW liquidity through programmatic orders, not CIP-30, the oSnap proposal it was filed against.", right],
  lost: ["dao", "The tokenswap in CIP-69 needed the Treasury Safe to sign the CoW order; the signing library is standard Safe infrastructure even if the proposal does not print its address.", 0],
  aexp: ["appellant", "The solver rewards renewal should have required a fresh budget report before the transfer; please have a new panel read the proposal again.", 0],
};
// in filing order, so each check is judged before its own judge deadline
for (const k of ["asv", "dev", "won", "lost", "unc", "aexp", "gate", "para"]) {
  let c = await v("rg", "get_check", [D[k]]);
  if (c.status === "PROVISIONAL") c = await judgeRule("filer", D[k]);
  if (APPEAL[k] && c.status === "CONTESTABLE") {
    const [role, text, alt] = APPEAL[k];
    const out = await w(role, "rg", "appeal", [D[k], text, alt], BOND);
    if (out.r?.ok === false) log("  appeal refused:", out.r.reason);
  }
}
const R = {};
for (const k of Object.keys(D)) R[k] = await v("rg", "get_check", [D[k]]);
expect("CIP-30 is AS_VOTED", R.asv.ruling === "AS_VOTED", R.asv.ruling_summary);
expect("appeals were filed inside the window", R.won.status === "APPEALED" && R.lost.status === "APPEALED" && R.aexp.status === "APPEALED", `${R.won.status} ${R.lost.status} ${R.aexp.status}`);
expect("CIP-16 batch is DEVIATES", R.dev.ruling === "DEVIATES", R.dev.ruling_summary);
expect("6,000,000 COW against CIP-30 is DEVIATES (CIP-30 never names the Treasury)", R.won.ruling === "DEVIATES", R.won.ruling_summary);
expect("CIP-69 Treasury call is DEVIATES", R.lost.ruling === "DEVIATES", R.lost.ruling_summary);
expect("67 WETH against CIP-28 is UNCLEAR (no amount on the Treasury's own line) and FINAL at once", R.unc.ruling === "UNCLEAR" && R.unc.status === "FINAL", R.unc.ruling_summary);
expect("CIP-29 is AS_VOTED", R.aexp.ruling === "AS_VOTED", R.aexp.ruling_summary);
for (const k of ["won", "lost", "aexp"]) R[k] = await v("rg", "get_check", [D[k]]);

// --- appeals: the fresh panel
for (const k of ["won", "lost"]) {
  const c = await v("rg", "get_check", [D[k]]);
  if (c.status === "APPEALED") await judgeRule("filer", D[k]);
}
R.won = await v("rg", "get_check", [D.won]);
R.lost = await v("rg", "get_check", [D.lost]);
expect("appeal naming CIP-37 wins: AS_VOTED, bond refunded", R.won.final_verdict === "AS_VOTED" && R.won.final_how === "APPEAL_RULED", R.won.appeal_summary);
expect("appeal with words only loses: DEVIATES stands, bond to the filer", R.lost.final_verdict === "DEVIATES" && R.lost.settlement.some((m) => /appeal bond to the filer/.test(m[0])), JSON.stringify(R.lost.settlement));

// --- finalize after the 90 s window
for (const k of ["asv", "dev", "gate", "para"]) {
  const c = await v("rg", "get_check", [D[k]]);
  if (c.status === "CONTESTABLE") { await waitPast(c.contest_deadline, `check #${D[k]} contest window`); await w("filer", "rg", "finalize", [D[k]]); }
}
R.asv = await v("rg", "get_check", [D.asv]);
R.dev = await v("rg", "get_check", [D.dev]);
expect("AS_VOTED final: stake to the DAO pledge", R.asv.final_verdict === "AS_VOTED" && R.asv.settlement.some((m) => /stake to the DAO pledge/.test(m[0])), JSON.stringify(R.asv.settlement));
expect("DEVIATES final: pledge slashed, bounty to the filer", R.dev.final_verdict === "DEVIATES" && BigInt(R.dev.slash) > 0n && R.dev.bounty_to === who("filer"), `slash ${R.dev.slash} severity ${R.dev.severity}`);
{
  R.gate = await v("rg", "get_check", [D.gate]);
  expect("recent 200,000 BAL transfer against CIP-69 is DEVIATES, final", R.gate.final_verdict === "DEVIATES", R.gate.ruling_summary);
  const g = await grant(treas, "release tranche 2");
  expect("GrantGate refuses after a final DEVIATES on a recent execution: DEVIATES", g.carried_out === false && g.state === "DEVIATES", JSON.stringify(g));
}
// --- COMPLIANT: a FINAL AS_VOTED, no open check, and the patrol's own scan and heartbeat
{
  R.para = await v("rg", "get_check", [D.para]);
  expect("ParaSwap PIP-59 (40.203 WETH back to Bybit) is AS_VOTED, final", R.para.final_verdict === "AS_VOTED", R.para.ruling_summary);
  log(`→ patrol scans the ParaSwap Safe and records coverage on the demo registry (dao #${para})`);
  const out = execFileSync("npx", ["tsx", "scripts/patrol-run.ts", `--registry=${A.rg}`, "--state=../docs/demo/patrol-state-demo.json", `--only=${para}`, "--backfill=7200"],
    { cwd: new URL("../frontend/", import.meta.url).pathname, encoding: "utf8", timeout: 600_000 });
  const rep = JSON.parse(out.trim().split("\n").pop());
  log(`  patrol: scans ${JSON.stringify(rep.scans)} writes ${JSON.stringify(rep.writes.map((x) => [x.fn, x.ok, x.hash, x.note]))}`);
  const cov = await v("rg", "get_coverage", [para, PATROL]);
  expect("the patrol's coverage heartbeat is on chain (FINALIZED, read back)", cov.found === true && rep.writes.some((x) => x.fn === "record_coverage" && x.ok), JSON.stringify(cov));
  D.coverage = cov;
  const g = await grant(para, "release tranche 2");
  expect("GrantGate carries out the request only now: COMPLIANT", g.carried_out === true && g.state === "COMPLIANT", JSON.stringify(g));
}

// --- expiries (600 s)
{
  const c = await v("rg", "get_check", [D.exp]);
  if (c.status === "PROVISIONAL") { await waitPast(c.judge_deadline, `check #${D.exp} judge deadline`); await w("filer", "rg", "expire", [D.exp]); }
  const a = await v("rg", "get_check", [D.aexp]);
  if (a.status === "APPEALED") { await waitPast(a.appeal_deadline, `check #${D.aexp} appeal deadline`); await w("filer", "rg", "expire", [D.aexp]); }
}
R.exp = await v("rg", "get_check", [D.exp]);
R.aexp = await v("rg", "get_check", [D.aexp]);
expect("never judged: expire -> FINAL UNCLEAR, stake refunded", R.exp.final_verdict === "UNCLEAR" && R.exp.final_how === "EXPIRED_UNJUDGED");
{
  // an expired check proved nothing: the same execution and proposal can be filed again
  const e = await execId("cip24");
  const vid = await freshVote(CID.cip24, COW);
  let id = Number(await v("rg", "get_check_id_by_tx", ["ethereum", COW, TX.cip24[0]]));
  if (id === D.exp) {
    const out = await w("filer2", "rg", "file_check", [cow, e, vid, "demo: refiled after expiry"], STAKE);
    if (out.r?.ok === false) log("  refused:", out.r.reason);
    id = Number(await v("rg", "get_check_id_by_tx", ["ethereum", COW, TX.cip24[0]]));
  }
  D.refile = id;
  let c = await v("rg", "get_check", [id]);
  if (c.status === "PROVISIONAL") c = await judgeRule("filer", id);
  if (c.status === "CONTESTABLE") { await waitPast(c.contest_deadline, `check #${id} contest window`); await w("filer", "rg", "finalize", [id]); }
  R.refile = await v("rg", "get_check", [id]);
  expect("an expired check can be refiled and ruled", id !== D.exp && R.refile.final_verdict !== "", `check #${id} ${R.refile.final_verdict} ${R.refile.ruling_summary}`);
}
expect("appeal never judged: expire -> ruling stands, bond refunded", R.aexp.final_verdict === "AS_VOTED" && R.aexp.final_how === "APPEAL_EXPIRED");

// --- STALE_MONITORING: the same DAO once its heartbeat is older than the demo's 1 h limit
{
  const cfg = J(await connect({ address: dep.DaoStandingDemo.address, role: "filer" }).view("get_config", []));
  const cov = await v("rg", "get_coverage", [para, PATROL]);
  await waitPast(cov.block_time + cfg.stale_s, `the ParaSwap heartbeat to pass ${cfg.stale_s}s`);
  const g = await grant(para, "release tranche 3");
  expect("GrantGate refuses once coverage is stale: STALE_MONITORING", g.carried_out === false && g.state === "STALE_MONITORING", JSON.stringify(g));
}

// --- drain
for (const id of [cow, treas, para]) {
  const d = await v("rg", "get_dao", [id]);
  if (BigInt(d.pledge) > 0n && BigInt(d.withdraw_amount) === 0n) await w("dao", "rg", "request_withdrawal", [id, d.pledge]);
}
for (const id of [cow, treas, para]) {
  const d = await v("rg", "get_dao", [id]);
  if (BigInt(d.withdraw_amount) > 0n) { await waitPast(d.withdraw_executable_at || d.withdraw_at, `dao #${id} withdrawal delay and late window`); await w("filer", "rg", "execute_withdrawal", [id]); }
}
const payouts = [];
const rgBefore = await balanceOf(A.rg);
log(`registry eth_getBalance before claims: ${rgBefore}`);
for (const role of ["filer", "filer2", "dao", "appellant"]) {
  const owed = BigInt((await v("rg", "claimable_of", [who(role)])).claimable);
  if (owed === 0n) continue;
  log(`→ ${role} claim [] (owed ${owed})`);
  const p = await provenClaim(C[role].rg.send, who(role), owed);
  payouts.push({ role, ...p });
  log(`  ${p.ok ? "ARRIVED" : "NOT ARRIVED"} ${p.status} ${p.tx} ${p.to} before ${p.before} after ${p.after} (+${p.amount} - fee ${p.fee}) ${p.reasons.join("; ")}`);
  expect(`payout to ${role} arrived on chain (${owed} wei)`, p.ok, `tx ${p.tx}: ${p.to} ${p.before} -> ${p.after}`);
}
const L = await v("rg", "get_ledger");
const rgAfter = await balanceOf(A.rg);
log(`registry eth_getBalance after claims: ${rgAfter}`);
expect("ledger invariant holds", L.invariant_holds === true && L.views_match_storage === true, JSON.stringify(L));
expect("registry balance fell by exactly the total paid out", rgBefore - rgAfter === payouts.reduce((s, p) => s + BigInt(p.amount), 0n), `${rgBefore} -> ${rgAfter}`);
expect("demo drained: books hold 0 and eth_getBalance of the registry is 0", L.held_now === "0" && L.claimable === "0" && L.pledges === "0" && L.open === "0" && rgAfter === 0n, `held_now ${L.held_now}, eth_getBalance ${rgAfter}`);
const stats = await v("rg", "get_stats");
writeFileSync(new URL("../docs/seed-demo.json", import.meta.url), JSON.stringify({ registry: A.rg, checks: D, results, ledger: L, registry_balance: { before_claims: String(rgBefore), after_claims: String(rgAfter) }, payouts, stats,
  final: Object.fromEntries(Object.entries(R).map(([k, c]) => [k, { check_id: c.check_id, ruling: c.ruling, appeal_ruling: c.appeal_ruling, final: c.final_verdict, how: c.final_how, summary: c.appeal_summary || c.ruling_summary, settlement: c.settlement }])) }, null, 2) + "\n");
log(`\n${results.filter((r) => r.ok).length}/${results.length} demo expectations passed`);
