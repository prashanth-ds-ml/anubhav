import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Start from nothing (final demo plan, Nov 3): a visitor empties their workspace, learns from the records live, sees
// the evidence gate's verdicts, and the recorded scenarios get the recorded lessons back. Live calls are mocked here.

test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

/** The real session, shown as live-capable (the tests have no key; nothing here reaches a model). */
async function liveOn(page: Page) {
  await page.route("**/api/session", async (r) => {
    try {
      const res = await r.fetch();
      const s = await res.json();
      await r.fulfill({ response: res, json: { ...s, models: { ...s.models, "Muse Spark 1.3": { available: true, reason: null } }, live_runs_left: 8 } });
    } catch { /* the test ended while this was in flight */ }
  });
}

const LEARNED = {
  model: "muse-spark-1.3", cost_usd: 0.061, latency_s: 48.2, counts: { CANDIDATE: 1, REJECTED: 1, EXPIRED: 1 },
  lessons: [
    { lesson_id: "L-T01-001", kind: "site_access", state: "CANDIDATE", enforceable: true, what: "x", reason: "3 refusal(s) of vehicles over 22 ft, none delivered",
      display: "Lakshmi Agencies (old town godown, Jangaon · site C0003): no truck longer than 22 ft gets in" },
    { lesson_id: "L-T01-002", kind: "receiving_hours", state: "REJECTED", what: "x", reason: "late arrivals were received; a habit, not a rule",
      display: "Annapurna Mart (old town godown, Jangaon · site C0030): does not receive after 6 pm" },
    { lesson_id: "L-T01-003", kind: "closure", state: "EXPIRED", what: "x", reason: "the road reopened before today", display: "Kazipet: bridge closed (from 2026-08-01 to 2026-09-29)" },
  ],
};

test("with live mode on, Start from nothing leads; starting fresh empties the workspace, and a recorded scenario restores it", async ({ page }) => {
  await liveOn(page);
  await page.goto("/");
  await expect(page.locator(".sc-card article").first()).toHaveAccessibleName(/^S0 Start from nothing/);
  await page.getByRole("button", { name: "Start S0" }).click();
  const guide = page.getByRole("region", { name: /Scenario S0/ });
  await guide.getByRole("button", { name: "Start fresh" }).click();
  await expect(guide.getByRole("status")).toContainText("Started fresh: 0 lessons · 0 tools · agents at version 1");
  await page.goto("/#learning");
  await expect(page.getByRole("status", { name: "What this workspace knows" })).toContainText("0 lessons");
  await expect(page.getByRole("status", { name: "What this workspace knows" })).toContainText("started fresh");
  // A recorded scenario needs the recorded lessons: they come back when it starts.
  await page.goto("/");
  await page.getByRole("button", { name: "Start S1" }).click();
  await page.goto("/#learning/L-T01-002");
  await expect(page.getByRole("article", { name: "Lesson L-T01-002" })).toBeVisible();
});

test("learning from the records shows each stage, then every proposed rule with the gate's verdict and its evidence", async ({ page }) => {
  await liveOn(page);
  await page.route("**/api/fresh/learn*", (r) => r.fulfill({ json: LEARNED }));
  await page.goto("/#learning");
  const panel = page.getByRole("region", { name: "Learn from the records" });
  await panel.getByRole("button", { name: /Learn from the records/ }).click();
  const stages = panel.getByRole("list", { name: "Learning, step by step" });
  await expect(stages).toContainText(/Read the records: [\d,]+ delivery stops on [\d,]+ trips/);
  await expect(stages).toContainText("Code checked each rule against the full records: 1 hold, 1 rejected, 1 already over");
  const found = panel.getByRole("list", { name: "What it proposed, with the gate's verdict" });
  await expect(found.getByRole("listitem")).toHaveCount(3);
  await expect(found.getByRole("listitem").first()).toContainText("✓ evidence holds · waiting for a person");
  await expect(found.getByRole("listitem").first()).toContainText("no truck longer than 22 ft gets in");
  await expect(found).toContainText("✕ rejected by the gate");
  await expect(found).toContainText("already over: stored as expired");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});

test("without live mode, learning from the records says why and spends nothing", async ({ page }) => {
  await page.goto("/#learning");
  const panel = page.getByRole("region", { name: "Learn from the records" });
  await expect(panel.getByRole("button", { name: /Learn from the records/ })).toBeDisabled();
  await expect(panel).toContainText(/Live mode is off/);
});

test("lessons on screen name the godown in full; the gate lesson reads as a person would say it", async ({ page }) => {
  await page.goto("/#learning/L-T01-002");
  await expect(page.getByRole("article", { name: "Lesson L-T01-002" }).getByRole("heading", { level: 3 }))
    .toHaveText(/Lakshmi Agencies \(.+, Jangaon · site C0003\): no truck longer than 22 ft gets in/);
});
