/**
 * Settles a superseded registry and pays everything out, using only its own
 * permissionless exits: every open check is expired (past its active
 * deadline) or finalized (past its contest window), every pledge is withdrawn
 * by its controller, and every account claims. Ends with the registry's
 * eth_getBalance, which must be 0.
 *
 *   node drain_superseded.mjs --address=0x... > ../docs/superseded/<dir>/drain.log
 */
import { connect, accounts, argOf, returnedJson, sleep } from "./harness.mjs";
import { balanceOf, provenClaim } from "../tools/payouts.mjs";

const address = argOf("address");
if (!address) throw new Error("--address=<registry> is required");
const acc = accounts();
const ROLES = ["filer", "filer2", "dao", "appellant", "demo", "patrol"].filter((r) => acc[r]);
const who = (role) => acc[role].address.toLowerCase();
const C = Object.fromEntries(ROLES.map((r) => [r, connect({ address, role: r })]));
const J = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const v = async (fn, args = []) => J(await C.filer.view(fn, args));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const now = () => Math.floor(Date.now() / 1000);
async function w(role, fn, args) {
  log(`→ ${role} ${fn} ${JSON.stringify(args)}`);
  const out = await C[role].send(fn, args, 0n);
  log(`  ${out.ok ? "OK" : "REVERTED"} ${out.status} ${out.hash} ${out.ok ? JSON.stringify(returnedJson(out) ?? "").slice(0, 200) : (out.revertReason ?? "").slice(0, 160)}`);
  return out;
}
async function waitPast(t, label) {
  const s = Number(t) - now() + 5;
  if (s > 0) { log(`… waiting ${s}s for ${label}`); await sleep(s * 1000); }
}

log(`registry ${address}  eth_getBalance ${await balanceOf(address)}`);
log("ledger before", JSON.stringify(await v("get_ledger")));

// checks: a few passes, since an expired appeal can leave a ruling that still needs its window
const total = Number((await v("get_stats")).checks ?? 0);
for (let pass = 0; pass < 4; pass++) {
  let open = 0;
  for (let id = 1; id <= total; id++) {
    const c = await v("get_check", [id]);
    if (!c.found || c.status === "FINAL") continue;
    open++;
    if (c.status === "CONTESTABLE") {
      await waitPast(c.contest_deadline, `check #${id} contest window`);
      await w("filer", "finalize", [id]);
    } else {
      await waitPast(c.active_deadline, `check #${id} ${c.status} deadline`);
      await w("filer", "expire", [id]);
    }
  }
  if (!open) break;
}
for (let id = 1; id <= total; id++) {
  const c = await v("get_check", [id]);
  log(`check #${id} ${c.status} final=${c.final_verdict || "-"} how=${c.final_how || "-"}`);
}

// pledges: each controller withdraws everything
const daos = [];
for (let off = 0; ;) {
  const p = await v("get_daos", [off, 50]);
  daos.push(...(p.daos ?? []));
  if (p.done || !(p.daos ?? []).length) break;
  off = p.next_offset;
}
for (const d0 of daos) {
  const d = await v("get_dao", [d0.dao_id]);
  if (BigInt(d.pledge) === 0n) continue;
  const role = ROLES.find((r) => who(r) === String(d.controller).toLowerCase());
  if (!role) { log(`dao #${d.dao_id}: pledge ${d.pledge} held by controller ${d.controller}, not a test account`); continue; }
  if (BigInt(d.withdraw_amount) === 0n) await w(role, "request_withdrawal", [d.dao_id, String(d.pledge)]);
  const e = await v("get_dao", [d0.dao_id]);
  await waitPast(e.withdraw_executable_at || e.withdraw_at, `dao #${d.dao_id} withdrawal delay`);
  await w("filer", "execute_withdrawal", [d.dao_id]);
}

// claims
for (const role of ROLES) {
  const owed = BigInt((await v("claimable_of", [who(role)])).claimable);
  if (owed === 0n) continue;
  const p = await provenClaim(C[role].send, who(role), owed);
  log(`claim ${role} ${owed}: ${p.ok ? "ARRIVED" : "NOT ARRIVED"} ${p.status} ${p.tx} ${p.to} ${p.before} -> ${p.after} ${p.reasons.join("; ")}`);
}
const L = await v("get_ledger");
log("ledger after", JSON.stringify(L));
log(`registry eth_getBalance after: ${await balanceOf(address)}`);
