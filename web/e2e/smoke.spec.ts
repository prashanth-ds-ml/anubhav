import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const PLAN = "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.";
const TOOL = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?";

test("dashboard loads real orders, fleet and company", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Anubhav" })).toBeVisible();
  await expect(page.getByRole("row").nth(1)).toBeVisible({ timeout: 30_000 }); // first load can wait on the world
  await page.getByRole("tab", { name: "Fleet" }).click();
  await expect(page.getByRole("cell", { name: "V01" })).toBeVisible();
  await page.getByRole("tab", { name: "Company" }).click();
  await expect(page.getByRole("heading", { name: "Sri Kakatiya Logistics" })).toBeVisible();
  await expect(page.getByText("Service area")).toBeVisible();
  await expect(page.getByText(/Written rules \(\d+\)/)).toBeVisible();
});

test("a recorded team run shows the hand-off to Tool Forge", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.getByText("Planner hands off to Tool Forge")).toBeVisible();
  await expect(page.locator(".bubble.answer")).toBeVisible();
});

test("why this plan shows the lesson the plan used, and the checks", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  await page.getByRole("tab", { name: "Route plans and drafts" }).click();
  await expect(page.getByRole("note").filter({ hasText: "From a recorded run." })).toBeVisible(); // rebuilt from a recording: it cannot be approved here
  await page.getByText("Why this plan").first().click();
  await expect(page.getByText("Lessons used").first()).toBeVisible();
  await expect(page.getByRole("tabpanel").locator(".why").getByText("max 22 ft").first()).toBeVisible();
  await expect(page.getByText("create_dispatch_draft").first()).toBeVisible();
  await expect(page.getByText(/passed/).first()).toBeVisible();
});

test("ledger filters by decision type", async ({ page }) => {
  await page.goto("/#ledger");
  await expect(page.getByRole("row").nth(1)).toBeVisible();
  await page.getByLabel("Decision").selectOption("handoff");
  await expect(page.getByRole("row").nth(1)).toBeVisible();
  const kinds = await page.getByRole("row").evaluateAll((rs) => rs.slice(1).map((r) => r.querySelectorAll("td")[2]?.textContent));
  expect(kinds.length).toBeGreaterThan(0);
  expect(new Set(kinds)).toEqual(new Set(["Handed off work"]));
});

test("keyboard: prompts are reachable and show a focus ring", async ({ page }) => {
  await page.goto("/");
  const first = page.getByRole("group", { name: "Saved requests" }).getByRole("button").first();
  await first.focus();
  const outline = await first.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/^Started on/).first()).toBeVisible();
});

for (const width of [1024, 1440]) {
  test(`no horizontal scroll at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await page.getByRole("button", { name: TOOL }).click();
    await expect(page.locator(".bubble.answer")).toBeVisible();
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over).toBeLessThanOrEqual(0);
  });
}

for (const scheme of ["light", "dark"] as const) {
  test(`no contrast violations (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" }); // no fade-in, so axe sees final colours
    await page.goto("/");
    await page.getByRole("button", { name: TOOL }).click();
    await expect(page.locator(".bubble.answer")).toBeVisible();
    const res = await new AxeBuilder({ page }).withTags(["wcag2aa"]).analyze();
    expect(res.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
  });
}
