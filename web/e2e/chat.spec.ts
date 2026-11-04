import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

// The saved requests and what their recordings contain (see docs/Backend_Report.md, section 12).
const PLAN = "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.";
const NICKNAME = "Pedda godown load ki bandi pettu.";
const TOOL = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?"; // recorded with lessons off only
const AMBIGUOUS = "Warangal load ki bandi pettu.";

/** Serve a fixture file as the server would: named server-sent events, then `end`. */
const sse = (file: string) =>
  readFileSync(`fixtures/${file}`, "utf-8").split("\n").filter(Boolean).map((l) => JSON.parse(l))
    .map((e) => `event: ${e.type}\nid: ${e.seq}\ndata: ${JSON.stringify(e)}\n\n`).join("") + `event: end\ndata: {"stop":"answered","mode":"replay"}\n\n`;

async function serveFixture(page: Page, file: string) {
  await page.route(/\/api\/chat$/, (r) => r.fulfill({ json: { run_id: "fixture", mode: "replay", replay_of: "single" } }));
  await page.route(/\/api\/chat\/stream/, (r) => r.fulfill({ contentType: "text/event-stream", body: sse(file) }));
}

test("intro explains the product in the first view", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/never dispatches without a person/i)).toBeVisible();
  await expect(page.getByText("Replay mode: recorded runs")).toBeVisible();
});

test("chat leads: about 60% wide on desktop, first on narrow screens", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const chat = await page.locator("main.center").boundingBox();
  const dash = await page.locator("aside.right").boundingBox();
  const share = chat!.width / (chat!.width + dash!.width);
  expect(share).toBeGreaterThan(0.55);
  expect(share).toBeLessThan(0.65);
  await page.setViewportSize({ width: 390, height: 844 });
  const c2 = await page.locator("main.center").boundingBox();
  const d2 = await page.locator("aside.right").boundingBox();
  expect(c2!.y).toBeLessThan(d2!.y);
});

test("a real recorded run: the plan uses the learned 22 ft rule, and the label says what it is", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.locator(".bubble.user")).toHaveText(PLAN);
  const answer = page.locator(".bubble.answer");
  await expect(answer).toContainText("V08");
  await expect(answer).toContainText("22 ft");
  await expect(answer).toContainText("L-T01-002");
  await expect(page.locator(".recorded")).toHaveText(/Recorded run · 2026-10-29 · Muse Spark Open · lessons on/);
  await expect(page.getByRole("note").filter({ hasText: /example|scripted/i })).toHaveCount(0);
  await expect(page.locator(".card.draft")).toContainText("Validated");
});

test("with lessons off the same request plans the 32 ft truck", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel(/Use approved lessons/)).toBeEnabled();   // known once the workspace's lessons are read
  await page.getByLabel(/Use approved lessons/).uncheck();
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.locator(".bubble.answer")).toContainText("V11");
  await expect(page.locator(".recorded")).toContainText("lessons off");
});

test("a request recorded only with the other setting switches it, and says so", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByLabel(/Use approved lessons/);
  await expect(toggle).toBeChecked();
  await page.getByRole("button", { name: TOOL }).click(); // recorded with lessons off only
  await expect(toggle).not.toBeChecked();
  await expect(page.getByText(/saved run for this request is with lessons off, so I switched that setting/)).toBeVisible();
  await expect(page.locator(".bubble.answer")).toContainText("Thursday");
});

test("a hand-off to a teammate gets its own lane, and the delegate call finishes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.getByText("Planner hands off to Tool Forge")).toBeVisible();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  await expect(page.locator(".lane-head").filter({ hasText: "asked by Planner" })).toHaveCount(1);
  await expect(page.getByText("running…")).toHaveCount(0); // the delegate call is matched with its result, past the teammate's whole run
  await expect(page.getByText("Done (limit)")).toBeVisible(); // the teammate stopped at its limit and the Planner still answered
});

test("auto-scroll keeps the answer in view inside the chat", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  // The scroll is smooth, so wait for the condition itself rather than a fixed time.
  const fromEnd = () => page.locator(".chat-log").evaluate((e) => e.scrollHeight - e.scrollTop - e.clientHeight);
  await expect.poll(fromEnd).toBeLessThanOrEqual(2);
  const logBox = await page.locator(".chat-log").boundingBox();
  const answer = await page.locator(".bubble.answer").boundingBox();
  expect(answer!.y + answer!.height).toBeLessThanOrEqual(logBox!.y + logBox!.height + 2); // the end of the answer is on screen
});

test("the input has a visible label and Enter sends a saved request", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".starter").first()).toBeVisible(); // the saved requests have loaded
  const box = page.getByLabel("Ask the agents");
  await expect(box).toBeVisible();
  await box.fill(PLAN);
  await box.press("Enter");
  await expect(page.locator(".bubble.user")).toHaveText(PLAN);
  await expect(box).toHaveValue("");
});

test("Shift+Enter adds a line instead of sending", async ({ page }) => {
  await page.goto("/");
  const box = page.getByLabel("Ask the agents");
  await box.fill("first line");
  await box.press("Shift+Enter");
  await box.type("second line");
  await expect(box).toHaveValue("first line\nsecond line");
  await expect(page.locator(".bubble.user")).toHaveCount(0);
});

test("a paraphrase offers the closest saved request, one click runs it", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".starter").first()).toBeVisible(); // the saved requests have loaded
  const box = page.getByLabel("Ask the agents");
  await box.fill("plan a truck for the Lakshmi Agencies Jangaon order");
  await page.getByRole("button", { name: "Send" }).click();
  const chip = page.getByRole("button", { name: /^Run: / });
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.locator(".bubble.answer")).toContainText("Draft");
});

test("a request sent before the saved requests have loaded waits for them, instead of finding nothing", async ({ page }) => {
  await page.route("**/api/suggestions*", async (r) => { await new Promise((ok) => setTimeout(ok, 2500)); await r.continue(); });
  await page.goto("/");
  await page.getByLabel("Ask the agents").fill(PLAN);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/No saved run matches that/)).toHaveCount(0);
  await expect(page.locator(".bubble.answer")).toContainText("V08");
});

test("an unrelated request is answered honestly, with no fake run", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".starter").first()).toBeVisible(); // the saved requests have loaded
  await page.getByLabel("Ask the agents").fill("what is the weather");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/No saved run matches that/)).toBeVisible();
  await expect(page.locator(".run")).toHaveCount(0);
});

test("when the server has no recording for a request, the person is told and nothing is invented", async ({ page }) => {
  await page.route(/\/api\/chat$/, (r) => r.fulfill({ status: 404, json: { error: { code: "NO_REPLAY", message: "No saved run for this request and setting." } } }));
  await page.goto("/");
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.getByText(/No saved run for this request and setting\. Pick a saved request below\./)).toBeVisible();
  await expect(page.locator(".run")).toHaveCount(0);
});

test("a run that stops to ask a person shows the question, and is labelled as scripted", async ({ page }) => {
  await serveFixture(page, "needs_person.jsonl");
  await page.goto("/");
  await page.getByRole("button", { name: AMBIGUOUS }).click();
  await expect(page.locator(".bubble.answer strong", { hasText: "Waiting for you" })).toBeVisible();
  await expect(page.locator(".bubble.answer")).toContainText("Warangal lo ae site ki load veltundi?");
  await expect(page.locator(".bubble.answer")).toContainText("Replying needs a live run");
  await expect(page.getByRole("note").filter({ hasText: "Scripted example." })).toBeVisible();
  await expect(page.locator(".recorded")).toHaveCount(0);
});

test("a scripted retry run shows the retries and the tool-missing alert", async ({ page }) => {
  await serveFixture(page, "retry_tool_missing.jsonl");
  await page.goto("/");
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.getByText("Retry run_query, attempt 3 of 3")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "No tool for this" })).toBeVisible();
  await expect(page.locator(".card.step.err").first()).toContainText("no such column");
});

test("switching company starts a fresh conversation for that company", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: PLAN }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
  await page.getByRole("combobox", { name: "Company" }).selectOption("TNEW");
  await expect(page.locator(".bubble.user")).toHaveCount(0);
  await expect(page.getByText(/Bhadrakali Transport Co \(new\): a synthetic company/)).toBeVisible();
  await expect(page.getByRole("region", { name: "The problem and the idea" })).toBeVisible();
});

test("when the server cannot be reached, a bundled example still plays, and says so", async ({ page }) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/");
  await expect(page.getByRole("group", { name: "Saved requests" })).toBeVisible();
  await page.getByRole("button", { name: /Warangal load ki bandi pettu/ }).click();
  await expect(page.getByText(/server cannot be reached, so this plays a bundled example/)).toBeVisible();
  await expect(page.locator(".bubble.answer strong", { hasText: "Waiting for you" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("note").filter({ hasText: "Scripted example." })).toBeVisible();
});
