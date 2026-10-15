// node shot.mjs <url> <out.png> [width] [theme] [waitMs] [localStorage json]
import { chromium } from "playwright";
const [url, out, width = "1366", theme = "light", wait = "9000", ls = "{}"] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const ctx = await b.newContext({ viewport: { width: Number(width), height: 900 }, colorScheme: theme, deviceScaleFactor: 1 });
await ctx.addInitScript((s) => { for (const [k, v] of Object.entries(JSON.parse(s))) localStorage.setItem(k, v); }, ls);
const p = await ctx.newPage();
await p.goto(url, { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
await p.waitForTimeout(Number(wait));
const sw = await p.evaluate(() => document.documentElement.scrollWidth);
console.log("scrollWidth", sw, "viewport", width);
await p.screenshot({ path: out, fullPage: true });
await b.close();
