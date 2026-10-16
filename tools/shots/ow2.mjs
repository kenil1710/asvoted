import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const p = await (await b.newContext({ viewport: { width: 375, height: 900 } })).newPage();
await p.goto(process.argv[2], { waitUntil: "networkidle" }).catch(() => {});
for (let i = 0; i < 2; i++) {
  await p.waitForTimeout(2500);
  const r = await p.evaluate(() => [document.documentElement.scrollWidth, [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > 376 || e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX !== "visible" || e.getBoundingClientRect().right > 376).slice(0, 4).map((e) => e.tagName + "." + e.className.toString().slice(0, 60) + " " + e.textContent.slice(0, 40))]);
  console.log(JSON.stringify(r));
}
await b.close();
