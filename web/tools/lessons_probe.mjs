import { chromium } from "@playwright/test";

// Repeats "new visitor opens the Learning tab" and reports any /api call that did not return 200, with the body of the failure.
const base = process.argv[2] ?? "http://localhost:7870";
const b = await chromium.launch();
let bad = 0;
for (let i = 0; i < 12; i++) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const fails = [];
  const t0 = Date.now();
  p.on("response", async (r) => {
    if (r.url().includes("/api/") && r.status() !== 200) fails.push(`${Date.now() - t0}ms ${r.status()} ${r.url().replace(base, "").slice(0, 60)} ${(await r.text().catch(() => "")).slice(0, 160)}`);
  });
  const seen = [];
  p.on("response", async (r) => {
    if (!r.url().includes("/api/learning/lessons")) return;
    const body = await r.json().catch(() => null);
    seen.push(`${Date.now() - t0}ms ${r.status()} lessons returned: ${Array.isArray(body) ? body.length : "not a list"}`);
  });
  p.on("requestfailed", (r) => { if (r.url().includes("/api/")) fails.push(`${Date.now() - t0}ms FAILED ${r.url().replace(base, "").slice(0, 60)} ${r.failure()?.errorText}`); });
  await p.goto(base);
  await p.getByRole("tab", { name: "Learning", exact: true }).click();
  const ok = await p.getByRole("heading", { name: /^Active \(\d+\)$/ }).waitFor({ timeout: 60000 }).then(() => true, () => false);
  console.log(`run ${i}: ${ok ? "ok " : "BAD"}  non-200 responses: ${fails.length}`);
  if (!ok || fails.length) {
    bad++;
    console.log(fails.map((f) => "   " + f).join("\n"));
    console.log("   lessons requests:\n      " + seen.join("\n      "));
    console.log("   section text:", JSON.stringify((await p.locator("#panel").innerText().catch(() => "")).slice(0, 300)));
  }
  await ctx.close();
}
console.log(`bad ${bad} of 12`);
await b.close();
