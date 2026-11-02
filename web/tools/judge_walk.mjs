import { chromium } from "@playwright/test";
const OUT = process.argv[2];
const b = await chromium.launch();
const log = [];
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
p.on("console", (m) => ["error", "warning"].includes(m.type()) && log.push(`console ${m.type()}: ${m.text()}`));
p.on("pageerror", (e) => log.push("pageerror: " + e.message));
p.on("requestfailed", (r) => log.push("reqfail: " + r.url()));
await p.goto("http://localhost:7860/");
await p.getByRole("row").nth(1).waitFor({ timeout: 30000 });
await p.screenshot({ path: `${OUT}/01_first_view.png` });
log.push("TITLE: " + (await p.title()));
log.push("H1/H2/H3: " + JSON.stringify(await p.$$eval("h1,h2,h3", (e) => e.map((x) => x.textContent))));
log.push("visible text above fold chars: " + (await p.evaluate(() => document.body.innerText.length)));
// play retry run to the end
await p.getByRole("button", { name: /Hanamkonda lo/ }).click();
await p.waitForTimeout(2500);
await p.screenshot({ path: `${OUT}/02_mid_run.png` });
await p.getByText("Learning: candidate tool").waitFor({ timeout: 20000 });
await p.screenshot({ path: `${OUT}/03_end_run.png` });
log.push("chat scrolls? chat panel scrollHeight vs viewport: " + (await p.evaluate(() => [document.documentElement.scrollHeight, innerHeight])));
for (const t of ["Route plans and drafts", "Fleet", "Company", "Ledger", "Agents", "Learning", "Proof"]) {
  await p.getByRole("tab", { name: t }).click();
  await p.waitForTimeout(500);
  await p.screenshot({ path: `${OUT}/04_tab_${t.replace(/ /g, "_")}.png` });
}
// typed input?
log.push("text inputs on page: " + (await p.locator("input[type=text],textarea").count()));
// mobile
const m = await b.newContext({ viewport: { width: 390, height: 844 } });
const mp = await m.newPage();
await mp.goto("http://localhost:7860/"); await mp.waitForTimeout(3000);
await mp.screenshot({ path: `${OUT}/05_mobile.png` });
log.push("mobile hscroll: " + (await mp.evaluate(() => document.documentElement.scrollWidth - innerWidth)));
// keyboard: tab order first 8 stops
await p.goto("http://localhost:7860/"); await p.waitForTimeout(1500);
const stops = [];
for (let i = 0; i < 12; i++) { await p.keyboard.press("Tab"); stops.push(await p.evaluate(() => (document.activeElement?.textContent || document.activeElement?.tagName).trim().slice(0, 40))); }
log.push("tab stops: " + JSON.stringify(stops));
log.push("tabs have aria-controls/arrow keys? " + (await p.$$eval("[role=tab]", (e) => e.map((x) => x.getAttribute("aria-controls")))));
console.log(log.join("\n"));
await b.close();
