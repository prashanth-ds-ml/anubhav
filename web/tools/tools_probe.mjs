import { chromium } from "@playwright/test";

// Repeats "open Learning, check the first candidate" as a new visitor and logs every /api/tools call, to see where it goes wrong.
const base = process.argv[2] ?? "http://localhost:7870";
const b = await chromium.launch();
let bad = 0;
for (let i = 0; i < 10; i++) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const log = [];
  const t0 = Date.now();
  const cookies = [];
  p.on("response", async (r) => {
    if (!r.url().includes("/api/")) return;
    const sc = await r.headerValue("set-cookie").catch(() => null);
    if (sc) cookies.push(`${Date.now() - t0}ms ${r.url().replace(base, "").split("?")[0]} ${sc.split(";")[0].slice(0, 40)}`);
  });
  p.on("request", (r) => { if (r.url().includes("/api/tools")) log.push(`${Date.now() - t0}ms > ${r.method()} ${r.url().replace(base, "").slice(0, 70)}`); });
  p.on("response", async (r) => { if (r.url().includes("/api/tools")) log.push(`${Date.now() - t0}ms < ${r.status()} ${r.url().replace(base, "").slice(0, 50)} ${(await r.text().catch(() => "")).slice(0, 60).replace(/\n/g, " ")}`); });
  await p.goto(base);
  await p.getByRole("tab", { name: "Learning", exact: true }).click();
  const cand = p.getByRole("article", { name: "Candidate wnum_weekday_by_town" });
  await cand.waitFor();
  await cand.getByRole("button", { name: "Check this query" }).click();
  const ok = await p.getByRole("article", { name: "Checked wnum_weekday_by_town" }).waitFor({ timeout: 8000 }).then(() => true, () => false);
  console.log(`run ${i}: ${ok ? "ok " : "BAD"} sessions created: ${new Set(cookies.map((c) => c.split(" ").pop())).size} (set-cookie on ${cookies.length} responses)`);
  if (!ok) {
    bad++;
    console.log(cookies.join("\n"));
    console.log(`run ${i}: NO "Checked" card after 8 s`);
    console.log(log.join("\n"));
    console.log("alert:", await p.getByRole("alert").allTextContents());
    console.log("buttons:", await p.getByRole("button", { name: /Check this query|Checking/ }).evaluateAll((els) => els.map((e) => `${e.textContent}${e.disabled ? " (disabled)" : ""}`)));
  }
  await ctx.close();
}
console.log(`failed ${bad} of 10`);
await b.close();
