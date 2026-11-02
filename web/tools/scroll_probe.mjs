import { chromium } from "@playwright/test";

// Repeats the "click a run, wait for the answer" flow and records how far the chat is from its end over time.
const base = process.argv[2] ?? "http://localhost:7870";
const b = await chromium.launch();
let stuck = 0;
for (let i = 0; i < 14; i++) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 800 } });
  const p = await ctx.newPage();
  await p.goto(base);
  await p.locator(".starter").first().waitFor();
  await p.getByRole("button", { name: /Hanamkonda lo ae weekday/ }).click();
  await p.locator(".bubble.answer").waitFor();
  const samples = [];
  for (let t = 0; t < 25; t++) {
    samples.push(await p.locator(".chat-log").evaluate((e) => [e.scrollHeight, e.clientHeight, Math.round(e.scrollHeight - e.scrollTop - e.clientHeight)]));
    await p.waitForTimeout(120);
  }
  const last = samples.at(-1);
  if (last[2] > 2) {
    stuck++;
    console.log(`run ${i}: STUCK ${last[2]}px. [scrollHeight, clientHeight, fromEnd] over time:`);
    console.log(samples.map((s) => s.join("/")).join("  "));
  }
  await ctx.close();
}
console.log(`stuck ${stuck} of 14`);
await b.close();
