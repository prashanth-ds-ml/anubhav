import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A person's decisions on a lesson. Every test is a new visitor, so it starts with T01's lessons as the demo world has them:
// ten active (one of them an enforced rule, L-T01-002) and one that expired on arrival (L-T01-011).
const ADVICE = "L-T01-001"; // advice only: cannot become a rule
const RULE = "L-T01-002"; // an enforceable site rule
const EXPIRED = "L-T01-011";

const card = (page: Page, id: string) => page.locator("li.panel", { hasText: id });
const heading = (page: Page, text: string | RegExp) => page.getByRole("heading", { name: text });

async function openLessons(page: Page) {
  await page.goto("/");
  await page.getByRole("tab", { name: "Learning", exact: true }).click();
  await expect(heading(page, "Active (10)")).toBeVisible();
}
const undo = (page: Page, id: string) => page.getByRole("button", { name: new RegExp(`^Undo.*, ${id}$`) });

test("a person can undo an approval, which sends the lesson back to waiting, and approve it again", async ({ page }) => {
  await openLessons(page);
  await expect(page.getByText(/saved runs stay as they were recorded/)).toBeVisible();
  await undo(page, ADVICE).click();
  await expect(heading(page, "Waiting for a person (1)")).toBeVisible();
  await expect(heading(page, "Active (9)")).toBeVisible();
  await expect(card(page, ADVICE)).toContainText("Waiting for a person");

  await page.getByRole("button", { name: `Approve as advice, ${ADVICE}` }).click();
  await expect(heading(page, "Active (10)")).toBeVisible();
  await expect(heading(page, /Waiting for a person/)).toHaveCount(0);
  // Every step is on the timeline: the undo and the approval.
  await page.getByText(/Learning timeline/).click();
  await expect(page.getByText(/rollback/i).first()).toBeVisible();
});

test("rejecting needs a reason, and the lesson moves to rejected", async ({ page }) => {
  await openLessons(page);
  await undo(page, "L-T01-005").click();
  await page.getByRole("button", { name: "Reject…, L-T01-005" }).click();
  const send = page.getByRole("button", { name: "Reject it" });
  await expect(send).toBeDisabled();
  await page.getByLabel("Why reject it?").fill("Not true for this region.");
  await send.click();
  await expect(heading(page, "Rejected or retired (2)")).toBeVisible(); // the expired one, and this
  await expect(card(page, "L-T01-005")).toContainText("Rejected");
  await expect(heading(page, /Waiting for a person/)).toHaveCount(0);
});

test("only an enforceable lesson can become a rule, and a rule needs a note of what was verified", async ({ page }) => {
  await openLessons(page);
  await undo(page, ADVICE).click();
  await expect(page.getByRole("button", { name: `Approve as advice, ${ADVICE}` })).toBeVisible();
  await expect(page.getByRole("button", { name: `Approve as a rule…, ${ADVICE}` })).toHaveCount(0); // advice-only kind

  await undo(page, RULE).click();
  await page.getByRole("button", { name: `Approve as a rule…, ${RULE}` }).click();
  const send = page.getByRole("button", { name: "Approve as a rule" });
  await expect(send).toBeDisabled();
  await page.getByLabel(/What did you verify/).fill("Operator confirmed on a site visit.");
  await send.click();
  await expect(card(page, RULE)).toContainText("Active rule: code enforces it");
});

test("retiring needs a reason, and Undo brings the lesson back", async ({ page }) => {
  await openLessons(page);
  await page.getByRole("button", { name: `Retire…, ${ADVICE}` }).click();
  await expect(page.getByRole("button", { name: "Retire it" })).toBeDisabled();
  await page.getByLabel("Why retire it?").fill("No longer true.");
  await page.getByRole("button", { name: "Retire it" }).click();
  await expect(card(page, ADVICE)).toContainText("Retired");
  await expect(heading(page, "Active (9)")).toBeVisible();

  await undo(page, ADVICE).click();
  await expect(card(page, ADVICE)).toContainText("Active advice");
  await expect(heading(page, "Active (10)")).toBeVisible();
});

test("a lesson that expired on arrival has nothing to undo, so it offers no buttons", async ({ page }) => {
  await openLessons(page);
  await expect(card(page, EXPIRED)).toContainText("Expired");
  await expect(card(page, EXPIRED).getByRole("button")).toHaveCount(0);
});

test("cancel closes the reason box and changes nothing", async ({ page }) => {
  await openLessons(page);
  await page.getByRole("button", { name: `Retire…, ${ADVICE}` }).click();
  await page.getByLabel("Why retire it?").fill("changed my mind");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByLabel("Why retire it?")).toHaveCount(0);
  await expect(heading(page, "Active (10)")).toBeVisible();
});

test("when the server refuses, the person is told why and the lesson is unchanged", async ({ page }) => {
  await page.route("**/api/learning/lessons/*/decide*", (r) =>
    r.fulfill({ status: 409, json: { error: { code: "CONFLICT", message: "That lesson cannot be changed right now." } } }));
  await openLessons(page);
  await undo(page, ADVICE).click();
  await expect(card(page, ADVICE).getByRole("alert")).toContainText("That lesson cannot be changed right now.");
  await expect(heading(page, "Active (10)")).toBeVisible();
});

test("the lesson controls and the reason box pass the accessibility check", async ({ page }) => {
  await openLessons(page);
  await page.getByRole("button", { name: `Retire…, ${ADVICE}` }).click();
  await expect(page.getByLabel("Why retire it?")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target.join(" ")} ${n.html.slice(0, 90)}`).join(" | ")}`)).toEqual([]);
});
