import { test, expect } from "@playwright/test";

const PLAN = "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.";
const TOOL = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?";

test("loop steps explain themselves; Approve and Improve are marked as outside a run", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".loop li", { hasText: /^Approve:/ })).toHaveAttribute("title", /outside a run/);
  await expect(page.locator(".loop li", { hasText: /^Verify:/ })).toHaveAttribute("title", /checks every draft/);
});

test("Approve and Improve never light up during or after a run", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  const seen = new Set<string>();
  for (let i = 0; i < 60; i++) {
    for (const t of await page.locator(".loop li.on").allTextContents()) seen.add(t.split(":")[0].trim());
    if (await page.locator(".bubble.answer").count()) break;
    await page.waitForTimeout(100);
  }
  expect(seen.has("Approve")).toBe(false);
  expect(seen.has("Improve")).toBe(false);
  await expect(page.locator(".loop li.on")).toHaveCount(0); // nothing lit once the run is done
});

test("real data carries no sample badge; a draft rebuilt from a recording says so", async ({ page }) => {
  await page.goto("/");
  for (const tab of ["Orders", "Fleet", "Company", "Agents", "Learning", "Proof"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("note")).toHaveCount(0);
  }
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  await page.getByRole("tab", { name: "Route plans and drafts" }).click();
  await expect(page.getByRole("note").filter({ hasText: "From a recorded run." })).toBeVisible();
});

test("plain-language labels replace jargon", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Agent roster").getByText("Safety checks (code)")).toBeVisible();
  await page.getByRole("tab", { name: "Agents" }).click();
  await expect(page.getByText("Things it knows about this company").first()).toBeVisible();
  await expect(page.getByText("Improvement over versions: not measured yet").first()).toBeVisible();
  await expect(page.getByText("Held-out score")).toHaveCount(0);
});

test("Plan a truck fills the box; replay offers the closest saved request", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".starter").first()).toBeVisible(); // the saved requests have loaded
  const row = page.getByRole("row").filter({ hasText: "Lakshmi Agencies" }).first();
  await row.getByRole("button", { name: "Plan a truck" }).click();
  const box = page.getByLabel("Ask the agents");
  await expect(box).toHaveValue(/Plan a truck for Lakshmi Agencies, Jangaon order/);
  await expect(box).toBeFocused();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: /^Run: Plan a truck for tomorrow/ })).toBeVisible();
});

test("orders are formatted for people", async ({ page }) => {
  await page.goto("/");
  const first = page.getByRole("row").nth(1);
  await expect(first).toContainText(/\d{1,3}(,\d{2,3})*(,\d{3})? kg/);
  await expect(first).toContainText(/Window \d\d:\d\d-\d\d:\d\d/);
  await expect(page.getByText(/Open orders for delivery on 30 Oct/)).toBeVisible();
});
