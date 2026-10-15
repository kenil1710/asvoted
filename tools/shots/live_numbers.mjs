// Compares numbers rendered on the live site with direct contract reads, and
// measures page width at 375 px. Prints one JSON line.
import { chromium } from "playwright";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const require = createRequire(new URL("../../test/package.json", import.meta.url));
const { createClient } = require("genlayer-js");
const { studioDevnet } = require("genlayer-js/chains");
const [site, reg] = process.argv.slice(2);
const dep = JSON.parse(readFileSync(new URL("../../deployments.json", import.meta.url), "utf8")).contracts;
const relay = process.env.STUDIO_RPC;
const chain = relay ? { ...studioDevnet, rpcUrls: { ...studioDevnet.rpcUrls, default: { ...studioDevnet.rpcUrls.default, http: [relay] } } } : studioDevnet;
const client = createClient({ chain });
const plain = (v) => (v instanceof Map ? Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)])) : typeof v === "bigint" ? Number(v) : v);
const view = async (a, f, args = []) => { const r = await client.readContract({ address: a, functionName: f, args }); return typeof r === "string" ? JSON.parse(r) : plain(r); };
const gen = (w, places = 4) => { const v = BigInt(w); const whole = v / 10n ** 18n; const frac = (v % 10n ** 18n).toString().padStart(18, "0").slice(0, places).replace(/0+$/, ""); return frac ? `${whole}.${frac}` : `${whole}`; };
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
async function grab(path, width = 1280, wait = 14000) {
  const ctx = await b.newContext({ viewport: { width, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(site + path, { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(wait);
  const vals = await p.$$eval("[data-k]", (els) => els.map((e) => [e.getAttribute("data-k"), e.textContent.trim()]));
  const w = await p.evaluate(() => document.documentElement.scrollWidth);
  await ctx.close();
  return { vals: Object.fromEntries(vals), w };
}
const st = await view(reg, "get_stats");
const L = await view(reg, "get_ledger");
const LD = await view(dep.AsVotedRegistryDemo.address, "get_ledger");
const d1 = await view(reg, "get_dao", [1]);
const expect = {
  checks: String(st.checks), "final:AS_VOTED": String(st["final:AS_VOTED"]), "final:DEVIATES": String(st["final:DEVIATES"]),
  "final:UNCLEAR": String(st["final:UNCLEAR"]), daos: String(st.daos), pledges: gen(L.pledges, 2),
  "Canonical registry:received": gen(L.received) + " GEN", "Canonical registry:open": gen(L.open) + " GEN", "Canonical registry:claimable": gen(L.claimable) + " GEN",
  "Canonical registry:held_now": gen(L.held_now) + " GEN", "Demo registry:received": gen(LD.received) + " GEN", "Demo registry:held_now": gen(LD.held_now) + " GEN",
  "Demo registry:claimed": gen(LD.claimed) + " GEN",
  "dao:final as voted": String(d1.as_voted), "dao:final deviates": String(d1.deviates), "dao:final unclear": String(d1.unclear), "dao:open checks": String(d1.open_checks),
};
const home = await grab("/"), ver = await grab("/verify"), dao = await grab("/dao/1");
const seen = { ...home.vals, ...ver.vals, ...dao.vals };
const lines = [], mismatch = [];
let compared = 0;
for (const [k, want] of Object.entries(expect)) {
  if (!(k in seen)) { mismatch.push([k, "not rendered", want]); continue; }
  compared++;
  const ok = seen[k] === want;
  lines.push(`${ok ? "=" : "≠"} ${k}: site "${seen[k]}" chain "${want}"`);
  if (!ok) mismatch.push([k, seen[k], want]);
}
const widths = [];
for (const p of ["/", "/daos", "/dao/1", "/check/1", "/file", "/patrol", "/docs", "/verify"]) widths.push({ p, w: (await grab(p, 375, 9000)).w });
await b.close();
console.log(JSON.stringify({ compared, mismatch, lines, widths }));
