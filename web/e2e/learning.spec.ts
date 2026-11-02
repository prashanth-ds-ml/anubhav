import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 3: the Learning tab shows why a lesson exists (its evidence, from the records) and its life.
// Numbers asserted here come from the demo world's records through /api/learning/lessons/{id}/evidence.

test("a gate lesson shows every trip to its site: three long trucks turned back, the learned limit drawn", async ({ page }) => {
  await page.goto("/#learning/L-T01-002");
  const detail = page.getByRole("article", { name: "Lesson L-T01-002" });
  const chart = detail.getByRole("figure", { name: "Evidence: every trip to this site" });
  await expect(chart).toContainText("Every trip to Lakshmi Agencies, by truck length");
  await expect(chart.locator(".ev-mark")).toHaveCount(18);
  await expect(chart.locator(".ev-mark.returned")).toHaveCount(3);
  await expect(chart.locator(".ev-guide-label")).toHaveText("limit it learned: 22 ft");
  await expect(chart.getByRole("img")).toHaveAttribute("aria-label", /18 trips: 3 turned back/);
  await expect(chart.getByRole("list", { name: "Legend" })).toContainText("turned back (3)");
  await chart.getByText("See the 18 trips as a table").click();
  await expect(chart.locator("tbody tr")).toHaveCount(18);
  await expect(detail.getByRole("link", { name: "This evidence as data (JSON)" })).toBeVisible();
});

test("the life of a lesson says who approved it: here a fixed review rule standing in for a person", async ({ page }) => {
  await page.goto("/#learning/L-T01-002");
  const life = page.getByRole("region", { name: "Life of this lesson" });
  await expect(life).toContainText("Proposed");
  await expect(life).toContainText("Evidence checked");
  await expect(life).toContainText("a fixed review rule standing in for a person");
  await expect(life).toContainText("Code blocks any plan that breaks it");
  await expect(life).toContainText("No end date");
});

test("the Kazipet road story: delays by week inside the closure and none after, the drivers' notes, and expiry", async ({ page }) => {
  await page.goto("/#learning/L-T01-011");
  const detail = page.getByRole("article", { name: "Lesson L-T01-011" });
  const chart = detail.getByRole("figure", { name: "Closure delays by week" });
  await expect(chart).toContainText("45 closure delays, all inside the closure, none after it");
  await expect(chart).toContainText("0 after it ended");
  const notes = detail.getByRole("region", { name: "What the drivers wrote" });
  await expect(notes.locator("li")).toHaveCount(28);
  await expect(notes).toContainText("Kazipet bridge closed, detour, 40 min late");
  await expect(notes.locator('li[lang="te"]').first()).toBeVisible();
  await expect(detail.getByRole("region", { name: "Life of this lesson" })).toContainText("Expired on arrival");
});

test("a lesson from a shared pack keeps its evidence with the company it came from", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("combobox", { name: "Company" }).selectOption("TNEW");
  await page.goto("/#learning/L-TNEW-002");
  await expect(page.getByRole("article", { name: "Lesson L-TNEW-002" })).toContainText("Its evidence is another company's records, which are not shared.");
});

test("S1's learning step lands on the gate lesson", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start S1" }).click();
  const guide = page.getByRole("region", { name: /Scenario S1/ });
  await guide.getByRole("button", { name: "Play the request without lessons" }).click();
  await expect(page.locator(".plan-card").last()).toBeVisible({ timeout: 60_000 });
  await guide.getByRole("button", { name: "See what it learned" }).click();
  await expect(page.getByRole("article", { name: "Lesson L-T01-002" })).toBeVisible();
  expect(new URL(page.url()).hash).toBe("#learning/L-T01-002");
});

test("S6 walks the road story step by step", async ({ page }) => {
  await page.goto("/?tour=S6");
  const guide = page.getByRole("region", { name: /Scenario S6/ });
  await expect(guide).toBeVisible();
  await guide.locator(".sc-step.big").click(); // open the road story
  await expect(page.getByRole("tab", { name: "Learning", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("article", { name: "Lesson L-T01-011" })).toBeVisible();
  await guide.locator(".sc-step.big").click(); // the drivers' notes
  await guide.locator(".sc-step.big").click(); // the delays chart
  await guide.locator(".sc-step.big").click(); // why it is no longer used
  await expect(guide.getByLabel("Step 4 done")).toBeVisible();
});

test("the Learning tab with its charts passes the accessibility check", async ({ page }) => {
  await page.goto("/#learning/L-T01-011");
  await expect(page.getByRole("figure", { name: "Closure delays by week" })).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});
