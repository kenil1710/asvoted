// For each listed treasury: is it a Safe, how many executed multisig txs, recent ones.
import { writeFileSync } from "node:fs";
const P = { ethereum: "eth", arbitrum: "arb1", optimism: "oeth", base: "base", polygon: "pol" };
const T = JSON.parse(process.argv[2]);
const out = {};
for (const [space, chain, addr] of T) {
  const base = `https://api.safe.global/tx-service/${P[chain]}/api/v1`;
  try {
    const info = await (await fetch(`${base}/safes/${addr}/`)).json();
    if (!info.owners) { console.log(space, chain, addr, "NOT A SAFE", JSON.stringify(info).slice(0, 80)); continue; }
    const txs = await (await fetch(`${base}/safes/${addr}/multisig-transactions/?executed=true&limit=100`)).json();
    out[`${space}|${chain}|${addr}`] = txs.results;
    const rec = txs.results.slice(0, 100);
    console.log(space, chain, addr, `v${info.version} ${info.threshold}/${info.owners.length} executed=${txs.count}`, "recent:", rec.slice(0, 3).map((r) => `${r.executionDate?.slice(0, 10)} ${r.dataDecoded?.method ?? (r.data ? r.data.slice(0, 10) : "eth")}`).join(", "));
  } catch (e) { console.log(space, chain, addr, "ERR", e.message); }
  await new Promise((r) => setTimeout(r, 400));
}
writeFileSync("safe_txs.json", JSON.stringify(out));
