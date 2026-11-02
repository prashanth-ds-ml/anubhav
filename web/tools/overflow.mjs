import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1024, height: 800 }, reducedMotion: "reduce" })).newPage();
await p.goto("http://localhost:7860/");
await p.getByRole("row").nth(1).waitFor({ timeout: 30000 });
await p.getByRole("button", { name: /Hanamkonda lo ae weekday/ }).click();
await p.locator(".bubble.answer").waitFor({ timeout: 30000 });
console.log(await p.evaluate(() => {
  const vw = document.documentElement.clientWidth, out = [];
  document.querySelectorAll("body *").forEach((e) => { const r = e.getBoundingClientRect(); if (r.right > vw + 1 && r.width > 0) out.push(`${e.tagName}.${e.className} right=${Math.round(r.right)} w=${Math.round(r.width)}`); });
  return JSON.stringify({ vw, sw: document.documentElement.scrollWidth, first: out.slice(0, 8) }, null, 1);
}));
await b.close();
