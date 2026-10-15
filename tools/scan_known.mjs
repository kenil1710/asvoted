const hub = "https://hub.snapshot.org/graphql";
const ids = process.argv.slice(2);
const NET = { "1": "ethereum", "42161": "arbitrum", "10": "optimism", "8453": "base", "137": "polygon" };
const r = await (await fetch(hub, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: `{spaces(first:100, where:{id_in:${JSON.stringify(ids)}}){id proposalsCount voting{type} treasuries{name address network}}}` }) })).json();
for (const s of r.data.spaces) {
  const t = (s.treasuries || []).filter((x) => NET[x.network]);
  if (t.length) console.log(s.id, s.proposalsCount, JSON.stringify(t.map((x) => [NET[x.network], x.address, x.name])));
}
