/**
 * The full pipeline for one real execution, idempotent step by step:
 *   VoteReader.read_space -> Registry.list_dao -> ExecReader.read_execution ->
 *   VoteReader.read_proposal -> VoteReader.read_names_at (if the text names ENS names) -> Registry.file_check (+ stake) ->
 *   AsVotedJudge.judge -> Registry.rule
 * Every step that already happened is detected by a view and skipped, so a
 * run that dropped can be started again with the same arguments.
 *
 *   node pipeline.mjs --set=final --reg=AsVotedRegistry --space=cow.eth --chain=ethereum \
 *        --safe=0x.. --tx=0x.. --nonce=27 --cid=bafk.. --note="..." [--role=filer] [--stop=file]
 */
import { readFileSync } from "node:fs";
import { connect, argOf, returnedJson, sleep } from "./harness.mjs";

const set = argOf("set", "final");
const dep = JSON.parse(readFileSync(new URL(set === "final" ? "../deployments.json" : `../deployments.${set}.json`, import.meta.url), "utf8")).contracts;
const role = argOf("role", "filer");
const regName = argOf("reg", "AsVotedRegistry");
const A = { er: dep.ExecReader.address, vr: dep.VoteReader.address, jg: dep.AsVotedJudge.address, rg: dep[regName].address };
const C = { er: connect({ address: A.er, role }), vr: connect({ address: A.vr, role }), jg: connect({ address: A.jg, role }), rg: connect({ address: A.rg, role }) };
const space = argOf("space"), chain = argOf("chain"), safe = argOf("safe").toLowerCase(), tx = argOf("tx").toLowerCase();
const nonce = Number(argOf("nonce")), cid = argOf("cid"), note = argOf("note", "");
const stop = argOf("stop", "");
const STAKE = 10n ** 17n;
const J = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const now = () => Math.floor(Date.now() / 1000);
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

async function step(label, c, fn, args, value = 0n) {
  log(`→ ${label}`);
  const out = await c.send(fn, args, value);
  log(`  ${out.ok ? "OK" : "FAILED"} ${out.status} ${out.seconds?.toFixed(0)}s ${out.hash} ${out.ok ? JSON.stringify(returnedJson(out) ?? out.returned ?? "").slice(0, 300) : out.revertReason?.slice(0, 200)}`);
  return out;
}

// 1. binding + listing
let daoId = Number(await C.rg.view("get_dao_id", [space, chain, safe]));
if (!daoId) {
  const bid = Number(await C.vr.view("get_binding_id", [space, chain, safe]));
  const b = bid ? J(await C.vr.view("get_binding", [bid])) : null;
  if (!b || now() - b.read_at > 3000) await step("read_space", C.vr, "read_space", [space, chain, safe]);
  await step("list_dao", C.rg, "list_dao", [space, chain, safe]);
  daoId = Number(await C.rg.view("get_dao_id", [space, chain, safe]));
}
log(`dao #${daoId}`);
if (!daoId) process.exit(2);
// 2. execution
let execId = Number(await C.er.view("get_execution_id", [chain, safe, tx]));
if (!execId) {
  await step("read_execution", C.er, "read_execution", [chain, safe, tx, nonce]);
  execId = Number(await C.er.view("get_execution_id", [chain, safe, tx]));
}
log(`execution #${execId}`);
if (!execId || stop === "exec") process.exit(execId ? 0 : 2);
// 3. check (filing needs a fresh proposal read)
let checkId = Number(await C.rg.view("get_check_id_by_tx", [chain, safe, tx]));
if (!checkId) {
  let voteId = Number(await C.vr.view("get_proposal_id", [cid, chain, safe]));
  const v = voteId ? J(await C.vr.view("get_proposal", [voteId])) : null;
  if (!v || now() - v.read_at > 3000) {
    const out = await step("read_proposal", C.vr, "read_proposal", [cid, chain, safe]);
    voteId = Number(await C.vr.view("get_proposal_id", [cid, chain, safe]));
    if (!out.ok && !voteId) process.exit(2);
  }
  log(`proposal #${voteId}`);
  if (stop === "vote") process.exit(0);
  // the proposal's ENS names as of the execution (its L1 block): a filing needs them
  const pv = J(await C.vr.view("get_proposal", [voteId]));
  const ev = J(await C.er.view("get_execution", [execId]));
  if (pv.ens_names?.length && ev.l1_block > 0 && !J(await C.vr.view("get_names_at", [voteId, ev.l1_block])).found) {
    await step("read_names_at", C.vr, "read_names_at", [voteId, ev.l1_block]);
  }
  const out = await step("file_check", C.rg, "file_check", [daoId, execId, voteId, note], STAKE);
  const r = returnedJson(out);
  if (r && r.ok === false) { log("refused:", r.reason); process.exit(3); }
  checkId = Number(await C.rg.view("get_check_id_by_tx", [chain, safe, tx]));
}
log(`check #${checkId}`);
if (!checkId || stop === "file") process.exit(checkId ? 0 : 2);
// 4. judge + rule
let c = J(await C.rg.view("get_check", [checkId]));
if (c.status === "PROVISIONAL" || c.status === "APPEALED") {
  const j = J(await C.jg.view("get_judgment", [A.rg, checkId, c.round]));
  if (!j.found) await step("judge", C.jg, "judge", [A.rg, checkId]);
  const j2 = J(await C.jg.view("get_judgment", [A.rg, checkId, c.round]));
  if (j2.found) await step("rule", C.rg, "rule", [checkId]);
  c = J(await C.rg.view("get_check", [checkId]));
}
log(`check #${checkId} ${c.status} ruling=${c.ruling} final=${c.final_verdict || "-"} :: ${c.ruling_summary}`);
console.log(JSON.stringify({ dao_id: daoId, exec_id: execId, check_id: checkId, status: c.status, ruling: c.ruling, summary: c.ruling_summary }));
