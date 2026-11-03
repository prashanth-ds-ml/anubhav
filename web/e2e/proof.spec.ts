import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 6: Proof & audit. Every figure is read from /api/proof or /api/proof/registry; these tests compare the page with
// those two routes, so a number on screen can't drift from the committed files.

test("Benchmarks: the per-company chart and the mining bars come from the result files", async ({ page }) => {
  const proof = await (await page.request.get("/api/proof")).json();
  const r11 = proof.find((p: { id: string }) => p.id === "EXP-011R");
  await page.goto("/#proof/bench");
  const chart = page.getByRole("region", { name: /learning made every company's plans correct more often/ });
  const fig = chart.getByRole("figure");
  for (const [name, c, x, y] of [["T01", "T01", "B", "C"], ["T02", "T02", "B", "C"], ["New company, day 1", "TNEW", "B", "E"]]) {
    const a = r11.summary[`${c}:${x}`], b = r11.summary[`${c}:${y}`];
    await expect(fig).toHaveAttribute("aria-label", new RegExp(`${name}: ${a.ok} to ${b.ok}, unsafe ${a.unsafe} to ${b.unsafe}`));
  }
  await expect(chart).toContainText("Not improved: real capacity, 0 of 6 with lessons at T01");
  const mining = page.getByRole("region", { name: /It learns the right things/ });
  await expect(mining.getByRole("list", { name: "Precision by experiment" }).getByRole("listitem")).toHaveCount(3);
  await expect(mining).toContainText("73% ✕ precision"); // EXP-008 repeat 0, the pre-registered measure, under the 85% bar
  await expect(mining).toContainText("90% ✓ precision");
  await expect(page.getByRole("region", { name: /Open weights match/ }).locator("tbody tr")).toHaveCount(2);
});

test("the scoreboard lists all 20 pre-registered experiments, and every missed bar is marked ✕", async ({ page }) => {
  const reg = (await (await page.request.get("/api/proof/registry")).json()).experiments as { id: string; verdict: string }[];
  expect(reg).toHaveLength(20);
  await page.goto("/#proof");
  const board = page.getByRole("list", { name: "20 experiments" });
  await expect(board.locator("details")).toHaveCount(20);
  await expect(board.locator("details.v-not-met")).toHaveCount(reg.filter((r) => r.verdict === "not_met").length);
  await expect(board.locator("details.v-met")).toHaveCount(reg.filter((r) => r.verdict === "met").length);
  for (const r of reg.filter((x) => x.verdict === "not_met")) {
    await expect(board.locator("details.v-not-met summary").filter({ hasText: r.id.replace("EXP-", "") }).first()).toContainText("✕");
  }
  // Opening one shows its bar, plan commit and result file.
  const nine = board.locator("details").filter({ hasText: /^.*009b/ }).first();
  await nine.locator("summary").click();
  await expect(nine).toContainText("Bar fixed in advance: pooled precision ≥ 0.85");
  await expect(nine.getByRole("link", { name: "result file" })).toHaveAttribute("href", /exp009b/);
  await expect(board).toContainText("--seed 4242");
});

test("Check our claims: one line per repeat, and a plan → result chain for every experiment", async ({ page }) => {
  await page.goto("/#proof");
  await page.getByRole("tab", { name: "Check our claims" }).click();
  expect(new URL(page.url()).hash).toBe("#proof/claims");
  const lessons = page.getByRole("region", { name: /Approved lessons lifted/ });
  await expect(lessons.getByRole("img")).toHaveAttribute("aria-label", /repeat 1: .*repeat 2: .*repeat 3: /);
  await lessons.getByText("See it as a table").click();
  await expect(lessons.locator("tbody tr")).toHaveCount(3);
  await expect(lessons).toContainText("bar set in advance: +25");
  await expect(page.getByRole("region", { name: /A new company went from/ })).toContainText("100% · all 3 repeats");
  const custody = page.getByRole("region", { name: /Check our claims: each one was fixed in advance/ });
  await expect(custody.locator("tbody tr")).toHaveCount(20);
  // Every row links its plan commit; every run experiment links its result commit and file.
  await expect(custody.locator('a[href*="/commit/"]')).toHaveCount(20 + 20); // every experiment has now run
  await expect(custody.getByRole("link", { name: "result file" })).toHaveCount(20);
  await expect(custody.locator("tbody tr").filter({ hasText: "EXP-009b" })).toContainText("(same commit)");
});

test("Proof shows the results on both models, and the per-company chart switches to Muse Spark 1.3", async ({ page }) => {
  await page.goto("/#proof/claims");
  const both = page.getByRole("region", { name: /Measured on both models/ });
  await expect(both).toContainText("Muse Spark Open (EXP-011R)");
  await expect(both).toContainText("Muse Spark 1.3 (EXP-015)");
  await expect(both.getByRole("row", { name: /Unwritten rules/ })).toContainText("45% → 90%");
  await expect(both.getByRole("row", { name: /Both bars met/ })).toContainText("3 of 3 ✓");
  await page.goto("/#proof/bench");
  await page.getByRole("button", { name: /EXP-015/ }).click();
  const chart = page.getByRole("region", { name: /learning made every company's plans correct more often/ });
  await expect(chart).toContainText("EXP-015 · Muse Spark 1.3");
  await expect(chart.getByRole("figure")).toHaveAttribute("aria-label", /T01: 19\/42 to 36\/42, unsafe 2 to 0/);
});

test("the raw data links on Proof answer", async ({ page }) => {
  await page.goto("/#proof");
  for (const name of ["/api/proof", "/api/proof/registry"]) {
    const href = await page.getByRole("link", { name, exact: true }).getAttribute("href");
    expect((await page.request.get(href!)).ok()).toBeTruthy();
  }
});

test("S3's last step opens the day-1 sharing chart", async ({ page }) => {
  await page.goto("/?tour=S3");
  const guide = page.getByRole("region", { name: /Scenario S3/ });
  await guide.getByRole("button", { name: "All steps" }).click();
  await guide.getByRole("button", { name: "See the measured result" }).click();
  expect(new URL(page.url()).hash).toBe("#proof/claims");
  await expect(page.getByRole("region", { name: /A new company went from 33% to 100%/ })).toBeVisible();
});

test("both Proof tabs pass the accessibility check", async ({ page }) => {
  for (const tab of ["bench", "claims"]) {
    await page.goto(`/#proof/${tab}`);
    await expect(page.locator("#proof-panel h3").first()).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  }
});
