import { chromium } from "@playwright/test";

// Records every scrollTo on the chat log (with the content height then) and every height change of an element inside it.
// Prints the events from the last scrollTo onward for the first run that ends short of the bottom.
const base = process.argv[2] ?? "http://localhost:7870";
const b = await chromium.launch();
for (let i = 0; i < 25; i++) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 800 } });
  const p = await ctx.newPage();
  await p.addInitScript(() => {
    const T0 = performance.now();
    const log = (window.__t = []);
    const now = () => Math.round(performance.now() - T0);
    const orig = Element.prototype.scrollTo;
    Element.prototype.scrollTo = function (...a) {
      if (this.classList?.contains("chat-log")) log.push(`${now()}ms CALL top=${a[0]?.top} h=${this.scrollHeight}`);
      return orig.apply(this, a);
    };
    addEventListener("DOMContentLoaded", () => {
      const watch = () => {
        const el = document.querySelector(".chat-log");
        if (!el) return setTimeout(watch, 20);
        const sizes = new WeakMap();
        const ro = new ResizeObserver((es) => es.forEach((x) => {
          const h = Math.round(x.contentRect.height), was = sizes.get(x.target);
          if (was !== undefined && was !== h) log.push(`${now()}ms RESIZE <${x.target.tagName.toLowerCase()} class="${String(x.target.className).slice(0, 36)}"> ${was} -> ${h}  text="${(x.target.textContent || "").slice(0, 40)}"`);
          sizes.set(x.target, h);
        }));
        const seen = new WeakSet();
        const obs = () => el.querySelectorAll("*").forEach((n) => { if (!seen.has(n)) { seen.add(n); ro.observe(n); } });
        new MutationObserver(obs).observe(el, { childList: true, subtree: true });
        obs();
      };
      watch();
    });
  });
  await p.goto(base);
  await p.locator(".starter").first().waitFor();
  await p.getByRole("button", { name: /Hanamkonda lo ae weekday/ }).click();
  await p.locator(".bubble.answer").waitFor();
  await p.waitForTimeout(1500);
  const end = await p.locator(".chat-log").evaluate((e) => Math.round(e.scrollHeight - e.scrollTop - e.clientHeight));
  if (end > 2) {
    console.log(`run ${i}: STUCK ${end}px`);
    const t = await p.evaluate(() => window.__t);
    const lastCall = t.map((x, k) => (x.includes("CALL") ? k : -1)).filter((k) => k >= 0).pop();
    console.log(t.slice(Math.max(0, lastCall - 3)).join("\n"));
    break;
  }
  await ctx.close();
}
await b.close();
