// Finalizes / expires every open check on a registry whose deadline has passed (permissionless exits).
import { readFileSync } from "node:fs";
import { connect, argOf, returnedJson } from "./harness.mjs";
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8")).contracts;
const rg = connect({ address: dep[argOf("reg", "AsVotedRegistry")].address, role: argOf("role", "filer2") });
const J = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const now = () => Math.floor(Date.now() / 1000);
const open = J(await rg.view("get_open_checks", [0, 50])).checks;
for (const c of open) {
  let fn = null;
  if (c.status === "CONTESTABLE" && now() > c.contest_deadline) fn = "finalize";
  if ((c.status === "PROVISIONAL" && now() > c.judge_deadline) || (c.status === "APPEALED" && now() > c.appeal_deadline)) fn = "expire";
  if (!fn) { console.log(`#${c.check_id} ${c.status} not past its deadline`); continue; }
  const out = await rg.send(fn, [c.check_id]);
  console.log(`#${c.check_id} ${fn} ${out.ok ? "OK" : "FAILED " + out.revertReason} ${JSON.stringify(returnedJson(out) ?? "")}`);
}
