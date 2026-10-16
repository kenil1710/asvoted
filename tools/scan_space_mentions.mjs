/**
 * Searches every proposal of the cow.eth and safe.eth Snapshot spaces (all
 * states, the whole history the hub returns) for the two addresses behind
 * seeds #7 and #14: title, body, discussion link and choices, case-insensitive,
 * full address (and in the body its first/last 8 hex digits). Output: docs/research/space_mentions.txt
 */
const A = ["0xc0fde70a65c7569fe919be57492228dee8cdb585", "0x03916d54cd6287325b6cf6a9a02a12f79676266c"];
for (const space of ["cow.eth", "safe.eth"]) {
  const all = [];
  for (let skip = 0; ; skip += 100) {
    const q = `{proposals(first:100,skip:${skip},where:{space:"${space}"},orderBy:"created",orderDirection:asc){id title created end state body discussion choices}}`;
    const r = await (await fetch("https://hub.snapshot.org/graphql", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q }) })).json();
    const p = r.data.proposals; all.push(...p); if (p.length < 100) break;
  }
  const d = (t) => new Date(t * 1000).toISOString().slice(0, 10);
  console.log(space, all.length, "proposals", d(all[0].created), "to", d(all.at(-1).created), "states", JSON.stringify(all.reduce((m, p) => (m[p.state] = (m[p.state] || 0) + 1, m), {})));
  for (const a of A) {
    const hit = all.filter((p) => (p.title + p.body + p.discussion + p.choices.join(" ")).toLowerCase().includes(a.slice(2)));
    const part = all.filter((p) => (p.body).toLowerCase().includes(a.slice(2, 10)) || p.body.toLowerCase().includes(a.slice(-8)));
    console.log(" ", a, "full:", hit.map((p) => `${p.title} (${d(p.end)}, ${p.state})`).join(" | ") || "none", "partial:", part.length);
  }
}
