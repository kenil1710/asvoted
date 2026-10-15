/**
 * One write or view against a deployed contract, with fee estimation and the
 * settle-aware outcome from harness.mjs.
 *   node tx.mjs --set=final --c=ExecReader --fn=read_execution --role=filer --args='["ethereum","0x..","0x..",27]' [--value=100000000000000000]
 *   node tx.mjs --set=final --c=AsVotedRegistry --view=get_stats --args='[]'
 */
import { readFileSync } from "node:fs";
import { connect, argOf } from "./harness.mjs";
const set = argOf("set", "final");
const dep = JSON.parse(readFileSync(new URL(set === "final" ? "../deployments.json" : `../deployments.${set}.json`, import.meta.url), "utf8"));
const address = dep.contracts[argOf("c")].address;
const args = JSON.parse(argOf("args", "[]"));
const { send, view } = connect({ address, role: argOf("role", "filer") });
if (argOf("view")) {
  const out = await view(argOf("view"), args);
  console.log(JSON.stringify(typeof out === "string" ? JSON.parse(out) : out, (k, v) => (typeof v === "bigint" ? v.toString() : v), 1));
} else {
  const out = await send(argOf("fn"), args, BigInt(argOf("value", "0")));
  console.log(JSON.stringify({ ok: out.ok, status: out.status, hash: out.hash, seconds: out.seconds, revert: out.revertReason?.slice(0, 300), returned: out.returned }, (k, v) => (typeof v === "bigint" ? v.toString() : v), 1));
  if (!out.ok) process.exitCode = 2;
}
