// Finds Snapshot spaces whose settings list treasuries on supported chains.
const hub = "https://hub.snapshot.org/graphql";
const q = async (query) => (await (await fetch(hub, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query }) })).json());
const NET = { "1": "ethereum", "42161": "arbitrum", "10": "optimism", "8453": "base", "137": "polygon" };
const out = [];
for (let skip = 0; skip < 3000; skip += 1000) {
  const r = await q(`{spaces(first:1000, skip:${skip}, orderBy:"proposalsCount", orderDirection:desc, where:{}){id name proposalsCount treasuries{name address network} voting{type}}}`);
  const sp = r.data?.spaces ?? [];
  if (!sp.length) { console.error("stop", JSON.stringify(r).slice(0, 200)); break; }
  for (const s of sp) {
    const t = (s.treasuries || []).filter((x) => NET[x.network] && /^0x[0-9a-fA-F]{40}$/.test(x.address));
    if (t.length && s.proposalsCount >= 15) out.push({ id: s.id, name: s.name, n: s.proposalsCount, t: t.map((x) => [NET[x.network], x.address, x.name]) });
  }
}
console.log(JSON.stringify(out, null, 1));
