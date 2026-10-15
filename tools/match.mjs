// Matches executed Safe txs to closed proposals of the same space that mention a recipient.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
const hub = "https://hub.snapshot.org/graphql";
const safes = JSON.parse(readFileSync("safe_txs.json", "utf8"));
const q = async (query) => (await (await fetch(hub, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query }) })).json());
function recips(tx) {
  const out = [];
  const walk = (to, value, dd) => {
    if (value && value !== "0") out.push(["ETH", to.toLowerCase()]);
    if (!dd) { out.push(["call", to.toLowerCase()]); return; }
    if (dd.method === "multiSend") {
      for (const v of dd.parameters?.[0]?.valueDecoded ?? []) walk(v.to, v.value, v.dataDecoded);
      return;
    }
    const p = Object.fromEntries((dd.parameters || []).map((x) => [x.name, x.value]));
    if (dd.method === "transfer") out.push([to.toLowerCase(), String(p.to || p._to || p.recipient || p.dst || Object.values(p)[0]).toLowerCase()]);
    else if (dd.method === "transferFrom") out.push([to.toLowerCase(), String(Object.values(p)[1]).toLowerCase()]);
    else if (dd.method === "approve") out.push([to.toLowerCase(), String(Object.values(p)[0]).toLowerCase()]);
    else out.push(["call:" + dd.method, to.toLowerCase()]);
  };
  walk(tx.to, tx.value, tx.dataDecoded);
  return out;
}
const props = {};
const res = [];
for (const [k, txs] of Object.entries(safes)) {
  const [space, chain, safe] = k.split("|");
  if (!props[space]) {
    const f = `props_${space}.json`;
    if (existsSync(f)) props[space] = JSON.parse(readFileSync(f, "utf8"));
    else {
      const r = await q(`{proposals(first:300, where:{space:"${space}", state:"closed"}, orderBy:"end", orderDirection:desc){id ipfs title body end type choices scores scores_state quorum}}`);
      props[space] = r.data?.proposals ?? [];
      writeFileSync(f, JSON.stringify(props[space]));
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
  for (const tx of txs) {
    if (!tx.transactionHash || !tx.isSuccessful) continue;
    const when = Date.parse(tx.executionDate) / 1000;
    const rs = recips(tx);
    const addrs = [...new Set(rs.map((r) => r[1]).filter((a) => /^0x[0-9a-f]{40}$/.test(a) && a !== safe.toLowerCase()))];
    const hits = props[space].filter((p) => p.end < when && addrs.some((a) => p.body.toLowerCase().includes(a)));
    if (!hits.length) continue;
    const p = hits[0];
    const allNamed = addrs.every((a) => p.body.toLowerCase().includes(a));
    res.push({ space, chain, safe, tx: tx.transactionHash, nonce: tx.nonce, date: tx.executionDate, method: tx.dataDecoded?.method ?? "raw", op: tx.operation, rs, proposal: p.id, ipfs: p.ipfs, title: p.title.slice(0, 70), end: new Date(p.end * 1000).toISOString().slice(0, 10), type: p.type, allNamed, lagDays: ((when - p.end) / 86400).toFixed(1) });
  }
}
writeFileSync("matches.json", JSON.stringify(res, null, 1));
for (const r of res) console.log(r.space.padEnd(18), r.chain.padEnd(8), r.date.slice(0, 10), r.method.padEnd(14), `lag ${r.lagDays}d`, r.allNamed ? "ALL" : "some", r.type, "|", r.title);
