import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 1: six main tabs with addresses, the scenario guide across tabs, and the live runs meter.

/** Make the real session report a live budget, without any key. */
async function liveSession(page: Page, used: number, leftToday = 50) {
  await page.route("**/api/session", async (r) => {
    const res = await r.fetch();
    const s = await res.json();
    const perVisit = s.caps.per_session;
    await r.fulfill({
      response: res,
      json: { ...s, models: { ...s.models, "Muse Spark 1.3": { available: used < perVisit && leftToday > 0, reason: used >= perVisit ? "This session used its 8 live runs. Use Replay, or run it locally." : leftToday === 0 ? "The demo's daily budget of 60 live runs is used up. Use Replay, or run it locally." : null } },
        live_runs_used: used, live_runs_left_today: leftToday, live_runs_left: Math.max(0, Math.min(perVisit - used, leftToday)) },
    });
  });
}

test("six main tabs, each with an address; the Desk keeps only the company's data", async ({ page }) => {
  await page.goto("/");
  const main = page.getByRole("tablist", { name: "Main" });
  await expect(main.getByRole("tab")).toHaveText(["Dispatch Desk", "Learning", "Tools", "Agents", "Runs", "Proof & audit"]);
  await expect(main.getByRole("tab", { name: "Dispatch Desk" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tablist", { name: "Company data" }).getByRole("tab")).toHaveText(["Orders", "Route plans and drafts", "Fleet", "Company", "Ledger"]);

  for (const [slug, name, heading] of [["learning", "Learning", "What it has learned"], ["tools", "Tools", "Repeated questions that could become tools"], ["runs", "Runs", "Runs you can inspect"]] as const) {
    await page.goto(`/#${slug}`);
    await expect(main.getByRole("tab", { name, exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("region", { name: "Agent chat" })).toBeHidden();
  }
  await main.getByRole("tab", { name: "Agents" }).click();
  expect(new URL(page.url()).hash).toBe("#agents");
  await page.goto("/#ledger");
  await expect(main.getByRole("tab", { name: "Dispatch Desk" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: "Ledger" })).toHaveAttribute("aria-selected", "true");
});

test("the runs list opens each run's full record", async ({ page }) => {
  await page.goto("/#runs");
  const link = page.getByRole("link", { name: "Raw record (JSON)" });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  const r = await page.request.get(href!);
  expect(r.ok()).toBeTruthy();
  expect(await r.json()).toHaveProperty("trace");
});

test("the scenario guide stays on screen across main tabs, and a run step brings you back to the Desk", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start S1" }).click();
  const guide = page.getByRole("region", { name: /Scenario S1/ });
  await guide.getByRole("button", { name: "Play the request without lessons" }).click();
  await expect(page.locator(".plan-card").last()).toBeVisible({ timeout: 60_000 });
  await guide.getByRole("button", { name: "See what it learned" }).click();
  await expect(page.getByRole("tab", { name: "Learning", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(guide).toBeVisible();
  await guide.getByRole("button", { name: "All steps" }).click();
  await guide.getByRole("button", { name: "Play the same request with lessons" }).click();
  await expect(page.getByRole("tab", { name: "Dispatch Desk" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".recorded").last()).toContainText("lessons on");
  // the first run is still in the conversation: the chat stayed loaded while Learning was open
  await expect(page.locator(".plan-card")).toHaveCount(2, { timeout: 60_000 });
});

test("without a key there is no live meter, just replay", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Replay mode: recorded runs")).toBeVisible();
  await expect(page.locator(".live-meter")).toHaveCount(0);
});

test("the live meter always shows how many live runs are left, block by block", async ({ page }) => {
  await liveSession(page, 2);
  await page.goto("/");
  const meter = page.getByRole("status", { name: /Live mode, Muse Spark 1.3/ });
  await expect(meter).toContainText("LIVE · Muse Spark 1.3");
  await expect(meter).toContainText("6 of 8 live runs left in this visit");
  await expect(meter.locator(".live-blocks .left")).toHaveCount(6);
  await expect(meter.locator(".live-blocks .used")).toHaveCount(2);
  await expect(page.getByRole("article", { name: /^S4 / })).toContainText("6 of 8 left");
  await expect(page.getByText(/6 live runs left in this visit/)).toBeVisible(); // the chat box repeats it
  const axe = await new AxeBuilder({ page }).include(".top").analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);
});

test("at zero the meter says so plainly, for the visit and for the day", async ({ page }) => {
  await liveSession(page, 8);
  await page.goto("/");
  await expect(page.locator(".live-meter")).toContainText("No live runs left in this visit. Recorded scenarios still work.");
  await expect(page.getByRole("button", { name: "Start S4" })).toBeDisabled();
  await page.unrouteAll();
  await liveSession(page, 1, 0);
  await page.reload();
  await expect(page.locator(".live-meter")).toContainText("Today's 60 live runs for this demo are used up. Recorded scenarios still work.");
});

test("on a phone the main tabs become a section menu", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("combobox", { name: "Section" }).selectOption("proof");
  expect(new URL(page.url()).hash).toBe("#proof");
  await expect(page.getByRole("combobox", { name: "Section" })).toHaveValue("proof");
});
