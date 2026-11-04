import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The Data tab: judges can read the records the agents work on, page by page, filtered by date.

const HEADING = "The records the agents work on";
const bodyRows = (page: Page) => page.locator(".data-table tbody tr");
const showing = (page: Page) => page.locator(".data-more p");
const totalOf = async (page: Page) => Number(((await showing(page).textContent()) ?? "").replace(/,/g, "").match(/of (\d+)/)?.[1] ?? NaN);

async function openData(page: Page) {
  await page.goto("/#data");
  await expect(page.getByRole("heading", { name: HEADING })).toBeVisible();
  await expect(showing(page)).toContainText("Showing");
}

test("pick a table, filter by date, load more", async ({ page }) => {
  await openData(page);
  await expect(page.getByRole("tab", { name: "Data", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: /^Orders/ })).toHaveAttribute("aria-pressed", "true");
  await expect(bodyRows(page).first()).toBeVisible();

  // Another table, from the quick buttons
  await page.getByRole("button", { name: /^Trips/ }).click();
  await expect(page.getByRole("button", { name: /^Trips/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("columnheader", { name: "vehicle_id" })).toBeVisible();
  await expect(bodyRows(page).first()).toBeVisible();
  const week = await totalOf(page);

  // All dates: more rows than the last week
  await page.getByLabel("All dates", { exact: true }).check();
  await expect.poll(() => totalOf(page)).toBeGreaterThan(week);
  await expect(bodyRows(page)).toHaveCount(50);
  await page.getByRole("button", { name: "Load more" }).click();
  await expect(bodyRows(page)).toHaveCount(100);
  await expect(showing(page)).toContainText("Showing 100 of");

  // A date with no records: the empty state, and a way back
  await page.getByLabel("All dates", { exact: true }).uncheck();
  await page.getByLabel("From", { exact: true }).fill("2020-01-01");
  await page.getByLabel("To", { exact: true }).fill("2020-01-02");
  await expect(page.getByText("No rows for these dates.")).toBeVisible();
  await page.getByRole("button", { name: "Show all dates" }).click();
  await expect(bodyRows(page).first()).toBeVisible();

  // Any table, from the full list; free text is shown as plain text
  await page.getByLabel("Table", { exact: true }).selectOption("driver_notes");
  await expect(page.getByRole("columnheader", { name: "text" })).toBeVisible();
  await expect(bodyRows(page).first()).toBeVisible();
  await expect(page.locator(".data-table td.free").first()).toBeVisible();
});

test("the Data tab passes the accessibility check", async ({ page }) => {
  await openData(page);
  await expect(bodyRows(page).first()).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});

for (const [w, h] of [[390, 844], [1440, 900]]) {
  test(`the Data tab does not scroll the page sideways at ${w} wide`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await openData(page);
    await page.getByLabel("All dates", { exact: true }).check();
    await expect(bodyRows(page)).toHaveCount(50);
    const m = await page.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
    expect(m.s).toBeLessThanOrEqual(m.c + 1);
  });
}
