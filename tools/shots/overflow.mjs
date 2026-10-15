import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const p = await (await b.newContext({ viewport: { width: 375, height: 800 } })).newPage();
await p.goto(process.argv[2], { waitUntil: "networkidle" }).catch(() => {});
await p.waitForTimeout(14000);
console.log(JSON.stringify(await p.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > 376).slice(0, 12).map((e) => [e.tagName, e.className.toString().slice(0, 80), Math.round(e.getBoundingClientRect().right), e.textContent.slice(0, 50)])), null, 1));
await b.close();
