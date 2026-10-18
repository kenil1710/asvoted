/**
 * One live patrol run from a terminal, with the patrol's own Studio Dev key
 * (read from test/.accounts.json, role "patrol"; never printed) and a local
 * state file instead of the patrol-state branch. Used by test/demo_paths.mjs
 * to have the patrol scan and record coverage on the DEMO registry.
 *
 *   cd frontend && npx tsx scripts/patrol-run.ts --registry=<0x..> --state=<file> [--only=3,4] [--backfill=7200] [--dry]
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { runPatrol } from "../src/lib/patrol";

async function main() {
const arg = (k: string) => process.argv.find((a) => a.startsWith(`--${k}=`))?.slice(k.length + 3);
const file = arg("state");
if (!file) throw new Error("--state=<file> is required");
const accounts = JSON.parse(readFileSync(join(process.cwd(), "..", "test", ".accounts.json"), "utf8"));
const backfill = arg("backfill") ? Number(arg("backfill")) : undefined;
const { report, state } = await runPatrol({
  dry: process.argv.includes("--dry"),
  key: accounts.patrol.key,
  state: existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : undefined,
  registry: arg("registry"),
  only: arg("only")?.split(",").map(Number),
  limits: backfill ? { initialBackfill: { ethereum: backfill, optimism: backfill * 6, base: backfill * 6, polygon: backfill * 6, arbitrum: backfill * 48 } } : undefined,
});
if (state) writeFileSync(file, JSON.stringify(state, null, 1) + "\n");
console.log(JSON.stringify(report, (_k, v) => (typeof v === "bigint" ? v.toString() : v)));
}

void main();
