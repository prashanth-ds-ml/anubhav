import { test, expect } from "@playwright/test";

const PLAN = "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.";
const TOOL = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?";

test("starters say what each saved request shows, in order; the rest are chips", async ({ page }) => {
  await page.goto("/");
  const cards = page.locator(".starter");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toContainText("1 Plan a truck: the agent drafts, a person decides");
  await expect(cards.nth(1)).toContainText("2 A nickname the company uses, found in its own records");
  await expect(cards.nth(2)).toContainText("3 A data question in Telugu: no tool fits, a teammate writes a query");
  await expect(page.locator(".more-requests .chip")).toHaveText(["Roman Telugu", "Telugu", "Mixed", "Ambiguous"]);
});

test("after the first run the starters shrink to compact chips (one set at a time)", async ({ page }) => {
  await page.goto("/");
  await page.locator(".starter").nth(1).click();
  await expect(page.locator(".starter")).toHaveCount(0);
  const chips = page.getByRole("group", { name: "Saved requests" }).getByRole("button");
  await expect(chips).toHaveCount(7);
  await expect(page.getByRole("group", { name: "Saved requests" })).toHaveCount(1);
  for (let i = 0; i < 7; i++) {
    const label = await chips.nth(i).getAttribute("aria-label");
    const visible = (await chips.nth(i).innerText()).trim();
    expect(label).toContain(visible); // the accessible name contains the visible text
  }
});

test("a tool call and its result are one step, and the teammate gets its own lane", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  expect(await page.locator(".card.step").count()).toBeGreaterThanOrEqual(5); // find_capability, delegate, and the Forge's tools
  await expect(page.getByText(/^Calls find_capability/)).toHaveCount(0); // no separate "Calls" card
  await expect(page.locator(".card.step", { hasText: "find_capability" })).toContainText("ok");
  await expect(page.locator(".lane-head").filter({ hasText: "asked by Planner" })).toHaveCount(1);
});

test("a drafted plan appears in the chat as a card with its order, the vehicle and the code's verdict", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: PLAN }).click();
  const card = page.locator(".card.draft");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Draft DR-9E10B9 on V08");
  await expect(card).toContainText("T01-O00879");
  await expect(card).toContainText("Validated");
  await expect(card).toContainText("Draft only. Nothing is dispatched until a person confirms.");
  await expect(page.locator(".card", { hasText: "Code check: passed" })).toHaveCount(0); // folded into the draft card
  await card.getByRole("button", { name: "See it under Route plans" }).click();
  await expect(page.getByRole("tab", { name: "Route plans and drafts" })).toHaveAttribute("aria-selected", "true");
  expect(new URL(page.url()).hash).toBe("#plans");
  await expect(page.getByRole("tabpanel")).toContainText("DR-9E10B9"); // the same draft, with its stops
  await expect(page.getByRole("tabpanel")).toContainText("Lakshmi Agencies, Jangaon");
});

test("Learning shows the same request with and without lessons: 32 ft against 22 ft", async ({ page }) => {
  await page.goto("/#learning");
  const sides = page.getByRole("region", { name: "Same request, with and without what it learned" }).locator("article");
  await expect(sides).toHaveCount(2);
  await expect(sides.nth(0)).toContainText("Without lessons");
  await expect(sides.nth(0)).toContainText("Vehicle V11: T32S, 32 ft");
  await expect(sides.nth(1)).toContainText("Vehicle V08: T22, 22 ft");
  await expect(page.getByText(/Both are recorded runs of Muse Spark Open/)).toBeVisible();
  await expect(page.getByRole("tabpanel")).toContainText("Active rule: code enforces it");
});

test("tabs have addresses: a link opens the right tab, and an unknown one falls back to Orders", async ({ page }) => {
  await page.goto("/#ledger");
  await expect(page.getByRole("tab", { name: "Ledger" })).toHaveAttribute("aria-selected", "true");
  await page.goto("/#nonsense");
  await expect(page.getByRole("tab", { name: "Orders" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Fleet" }).click();
  expect(new URL(page.url()).hash).toBe("#fleet");
});

test("a summary strip gives the company at a glance", async ({ page }) => {
  await page.goto("/");
  const kpis = page.getByLabel("At a glance");
  await expect(kpis).toContainText(/\d+\s*open orders/);
  await expect(kpis).toContainText(/\d+ t\s*to move/);
  await expect(kpis).toContainText(/\d+\s*vehicles/);
});

test("the header takes at most two rows of height on desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const box = await page.locator("header.top").boundingBox();
  expect(box!.height).toBeLessThan(120);
  await expect(page.getByText(/never dispatches without a person/)).toBeVisible();
});
