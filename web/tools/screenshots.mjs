// Captures README screenshots from the running site (default http://localhost:7860). Output: web/readme-assets/
// It plays saved runs, so the server must be in replay mode (the default). Run `npm run build` first.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:7860";
const OUT = new URL("../readme-assets/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const shot = (page, name) => page.screenshot({ path: `${OUT}${name}.png`, fullPage: false });
// The first visit loads the company in the background, so wait until no placeholder is left in the data panel.
const loaded = async (page) => {
  await page.locator("#panel .skeleton, #panel [aria-busy=true]").first().waitFor({ state: "detached", timeout: 60000 }).catch(() => {});
  // The three counters above the tabs show "..." until their numbers arrive.
  await page.waitForFunction(() => ![...document.querySelectorAll(".right *")].some((e) => e.children.length === 0 && ["...", "…"].includes(e.textContent.trim())), null, { timeout: 60000 }).catch(() => {});
};
const tab = async (page, name) => {
  await page.getByRole("tab", { name, exact: true }).click();
  await loaded(page);
  await page.waitForTimeout(400);
};

for (const [scheme, width] of [["light", 1440], ["dark", 1440], ["light", 1024]]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(BASE);
  await page.locator(".starter").first().waitFor({ timeout: 30000 });
  const main = scheme === "light" && width === 1440;
  if (main) {
    await loaded(page);
    await page.locator(".chat-log").evaluate((e) => e.scrollTo({ top: 0 }));
    await page.waitForTimeout(300);
    await shot(page, "start");
  }

  // Story 1: plan a truck, with the approved lessons.
  await page.locator(".starter").first().click();
  await page.locator(".bubble.answer").waitFor({ timeout: 30000 });
  await loaded(page);
  await page.waitForTimeout(800);
  await shot(page, `run-${scheme}-${width}`);

  if (main) {
    await tab(page, "Orders");
    await shot(page, "orders");
    await tab(page, "Route plans and drafts");
    const why = page.getByText("Why this plan").first();
    if (await why.count()) await why.click();
    await shot(page, "why-this-plan");
    await tab(page, "Ledger");
    await shot(page, "ledger");
    await tab(page, "Agents");
    await shot(page, "agents");
    await tab(page, "Learning");
    await page.waitForTimeout(800);
    await shot(page, "learning");
    await tab(page, "Proof");
    await page.waitForTimeout(800);
    await shot(page, "proof");
  }
  await ctx.close();
}
await browser.close();
console.log("saved to", OUT);
