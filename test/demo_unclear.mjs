/**
 * The demo's UNCLEAR path, run separately: in the main run the ExecReader
 * read of CIP-19 ended UNDETERMINED (validators disagreed, nothing was
 * written - tx 0x7b62c9110234be83d4a427b2664d7daea398668881d2a668ca7f4369e9d6c9e0),
 * so the filing never happened. Files CIP-19 on the demo registry, judges,
 * rules (UNCLEAR is final at once), claims the refund, and updates
 * docs/seed-demo.json's result for that path and its ledger.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { connect, accounts, returnedJson } from "./harness.mjs";
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8")).contracts;
const A = { er: dep.ExecReader.address, vr: dep.VoteReader.address, jg: dep.AsVotedJudge.address, rg: dep.AsVotedRegistryDemo.address };
const C = Object.fromEntries(Object.entries(A).map(([k, a]) => [k, connect({ address: a, role: "filer" })]));
const J = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const COW = "0xcA771eda0c70aA7d053aB1B25004559B918FE662";
const TX = "0x1fd579d7bbb8e7e8b8a6e2816f679ca55dddf36728615420d5a7f21c87d4870f";
const CID = "bafkreigeksmh3n7sxmon5y7vhow2vieuxoyhyq3u42ent6cbwq7sfenwpq";
const w = async (c, fn, args, value = 0n) => {
  log(`→ ${fn} ${JSON.stringify(args).slice(0, 100)}`);
  const out = await C[c].send(fn, args, value);
  log(`  ${out.ok ? "OK" : "REVERTED"} ${out.status} ${out.hash} ${JSON.stringify(returnedJson(out) ?? out.revertReason ?? "").slice(0, 200)}`);
  return out;
};
const v = async (c, fn, args = []) => J(await C[c].view(fn, args));
let eid = Number(await v("er", "get_execution_id", ["ethereum", COW, TX]));
if (!eid) { await w("er", "read_execution", ["ethereum", COW, TX, 9]); eid = Number(await v("er", "get_execution_id", ["ethereum", COW, TX])); }
let vid = Number(await v("vr", "get_proposal_id", [CID, "ethereum", COW]));
const p = vid ? await v("vr", "get_proposal", [vid]) : null;
if (!p || Date.now() / 1000 - p.read_at > 3000) { await w("vr", "read_proposal", [CID, "ethereum", COW]); vid = Number(await v("vr", "get_proposal_id", [CID, "ethereum", COW])); }
const dao = Number(await v("rg", "get_dao_id", ["cow.eth", "ethereum", COW]));
let cid = Number(await v("rg", "get_check_id_by_tx", ["ethereum", COW, TX]));
if (!cid) { await w("rg", "file_check", [dao, eid, vid, "demo: unclear"], 10n ** 17n); cid = Number(await v("rg", "get_check_id_by_tx", ["ethereum", COW, TX])); }
let c = await v("rg", "get_check", [cid]);
if (c.status === "PROVISIONAL") { await w("jg", "judge", [A.rg, cid]); await w("rg", "rule", [cid]); c = await v("rg", "get_check", [cid]); }
const ok = c.ruling === "UNCLEAR" && c.status === "FINAL" && c.settlement.some((m) => /stake refunded/.test(m[0]));
log(`${ok ? "PASS" : "FAIL"}  CIP-19 is UNCLEAR and FINAL at once, stake refunded  ${c.ruling_summary}`);
const me = accounts().filer.address.toLowerCase();
const cl = await v("rg", "claimable_of", [me]);
if (BigInt(cl.claimable) > 0n) await w("rg", "claim", []);
const L = await v("rg", "get_ledger");
const drained = L.held_now === "0" && L.claimable === "0" && L.pledges === "0" && L.open === "0";
log(`${drained && L.invariant_holds ? "PASS" : "FAIL"}  ledger after the UNCLEAR path: held_now ${L.held_now}, invariant ${L.invariant_holds}`);
const path = new URL("../docs/seed-demo.json", import.meta.url);
const doc = JSON.parse(readFileSync(path, "utf8"));
doc.results = doc.results.map((r) => (r.name.startsWith("CIP-19 is UNCLEAR") ? { name: "CIP-19 is UNCLEAR and FINAL at once (run by demo_unclear.mjs after an UNDETERMINED read)", ok, detail: c.ruling_summary } : r));
for (const r of doc.results) if (/ledger invariant|drains to exactly 0/.test(r.name)) { r.ok = r.name.includes("invariant") ? L.invariant_holds && L.views_match_storage : drained; r.detail = `after demo_unclear.mjs: held_now ${L.held_now}`; }
doc.checks.unc = cid;
doc.final.unc = { check_id: cid, ruling: c.ruling, final: c.final_verdict, how: c.final_how, summary: c.ruling_summary, settlement: c.settlement };
doc.ledger = L;
doc.undetermined_example = { tx: "0x7b62c9110234be83d4a427b2664d7daea398668881d2a668ca7f4369e9d6c9e0", what: "ExecReader.read_execution of CIP-19 ended UNDETERMINED; nothing was written; a later read succeeded" };
writeFileSync(path, JSON.stringify(doc, null, 2) + "\n");
log(`${doc.results.filter((r) => r.ok).length}/${doc.results.length} demo expectations now pass`);
