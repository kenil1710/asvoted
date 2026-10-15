/**
 * Files every seed in seeds.json on the CANONICAL registry through
 * pipeline.mjs (idempotent per step), one after another, and writes
 * docs/seed-canonical.json from contract state afterwards.
 *   node seed_canonical.mjs [--from=0]
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { argOf } from "./harness.mjs";
const seeds = JSON.parse(readFileSync(new URL("./seeds.json", import.meta.url), "utf8"));
const from = Number(argOf("from", "0"));
for (let i = from; i < seeds.length; i++) {
  const s = seeds[i];
  console.log(`\n=== seed ${i + 1}/${seeds.length}: ${s.space} ${s.title}`);
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const out = execFileSync("node", ["pipeline.mjs", "--set=final", "--reg=AsVotedRegistry", `--space=${s.space}`, `--chain=${s.chain}`,
        `--safe=${s.safe}`, `--tx=${s.tx}`, `--nonce=${s.nonce}`, `--cid=${s.cid}`, `--note=${s.title}`], { cwd: new URL(".", import.meta.url).pathname, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"], timeout: 3_600_000 });
      const last = out.trim().split("\n").pop();
      console.log(out.split("\n").filter((l) => /→|OK|FAILED|check #|refused/.test(l)).join("\n"));
      const r = JSON.parse(last);
      if (r.ruling) break;
      console.log(`  not ruled yet (attempt ${attempt}), retrying`);
    } catch (e) {
      console.log(`  pipeline exited ${e.status} (attempt ${attempt}): ${String(e.stdout ?? "").split("\n").slice(-4).join(" | ")}`);
    }
  }
}
console.log("\ndone");
