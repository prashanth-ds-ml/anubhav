import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 4: the Dispatch Desk payoff. The truck drawn against the gate it learned, what code checked, the same request in
// other languages, the end of S1 on one scale, the loop strip, decisions on a live draft, S4's retired-lesson card, and a
// first screen that fits a laptop.

const plan = (page: Page) => page.locator(".plan-card").last();

/** A recorded run stands in for a live one: its drafts come back as this visitor's own live drafts. */
async function asLiveDrafts(page: Page) {
  await page.route("**/api/dashboard/drafts?*", async (r) => {
    try {
      const body = await (await r.fetch()).json();
      await r.fulfill({ json: { ...body, source: "live", drafts: body.drafts.map((d: object) => ({ ...d, source: "live", status: "draft" })) } });
    } catch { /* the test ended while this request was in flight */ }
  });
}
test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

async function playS1WithoutLessons(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Start S1", exact: true }).click();
  const guide = page.getByRole("region", { name: /Scenario S1/ });
  await guide.getByRole("button", { name: "Play the request without lessons" }).click();
  await expect(plan(page)).toBeVisible({ timeout: 60_000 });
  return guide;
}

test("the plan card draws the 32 ft truck past the learned 22 ft gate line, and says only the rule says no", async ({ page }) => {
  await playS1WithoutLessons(page);
  const card = plan(page);
  const scale = card.getByRole("figure", { name: /Truck lengths against the gate limit of 22 ft/ });
  await expect(scale).toHaveAttribute("aria-label", /V11, 32 ft, too long/);
  await expect(scale).toContainText("learned from 3 turned-back trucks");
  // The bar ends past the gate line: 32 ft against 22 ft.
  const bar = await scale.locator(".ts-bar").boundingBox();
  const line = await scale.locator(".ts-limit").boundingBox();
  expect(bar!.x + bar!.width).toBeGreaterThan(line!.x);
  const checks = card.getByRole("group", { name: "What code checked" });
  await expect(checks).toContainText("Load fits (7,260 of 7,500 kg)");
  await expect(checks).toContainText("Final re-check");
  await expect(checks).toContainText("The code checks passed. Only the learned rule says no.");
  await expect(card.getByRole("button", { name: /Approve draft/ })).toHaveCount(0); // a recorded draft offers no decision
});

test("the same request plays in its other recorded languages", async ({ page }) => {
  await playS1WithoutLessons(page);
  const chips = page.getByRole("group", { name: "The same request in other languages" }).last();
  await expect(chips.getByRole("button", { name: "English" })).toBeVisible();
  await chips.getByRole("button", { name: "తెలుగు" }).click();
  await expect(page.locator(".bubble.user").last()).toContainText("రేపు జనగామ");
  await expect(page.locator(".recorded").last()).toContainText("lessons off"); // the same setting as the run it came from
});

test("S1's end puts both trucks on one scale, frames it, and lights Approve and Improve in the loop", async ({ page }) => {
  const guide = await playS1WithoutLessons(page);
  const loop = page.getByRole("list", { name: "Closed loop" });
  await expect(loop.locator("li.lit")).toHaveCount(0);
  await guide.getByRole("button", { name: "See what it learned" }).click();
  await guide.getByRole("button", { name: "Undo and redo the approval yourself" }).click();
  await expect(loop.locator("li.lit")).toHaveText(["Approve ✓: reached in this scenario. A person approves anything learned. This happens outside a run."]);
  await guide.getByRole("button", { name: "Play the same request with lessons" }).click();
  await expect(guide).toContainText("All 4 steps done. Same model, same request.");
  const scale = guide.getByRole("figure", { name: /Truck lengths against the gate limit of 22 ft/ });
  await expect(scale).toHaveAttribute("aria-label", /Without lessons: V11, 32 ft, too long; With the approved lesson: V08, 22 ft, fits/);
  const [long, short] = await scale.locator(".ts-bar").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().width));
  expect(long / short).toBeCloseTo(32 / 22, 1); // drawn to scale
  await expect(loop.locator("li.lit")).toHaveCount(2);
  await guide.getByRole("button", { name: /Next scenario: S2/ }).click();
  await expect(page.getByRole("region", { name: /Scenario S2/ })).toBeVisible();
  await expect(loop.locator("li.lit")).toHaveCount(0);
});

test("a live draft can be approved, re-checked in code, or rejected with a note; neither dispatches", async ({ page }) => {
  await asLiveDrafts(page);
  const sent: unknown[] = [];
  await page.route("**/api/dashboard/drafts/*/decide*", async (r) => {
    const b = r.request().postDataJSON();
    sent.push(b);
    await r.fulfill({ json: { draft_id: "x", status: b.decision === "approve" ? "approved" : "rejected", revise_run_id: null } });
  });
  await playS1WithoutLessons(page);
  const card = plan(page);
  await expect(card).toContainText("Live draft, not dispatched");
  await card.getByRole("button", { name: /Reject draft .* with a note/ }).click();
  const send = card.getByRole("button", { name: "Reject it" });
  await expect(send).toBeDisabled();
  await card.getByLabel("What is wrong with this plan?").fill("The gate is too small for 32 ft.");
  await send.click();
  await expect(card.getByRole("status")).toContainText("Rejected by you, with your note");
  expect(sent[0]).toMatchObject({ decision: "reject", notes: "The gate is too small for 32 ft.", revise: false }); // no new live run
});

test("approving a live draft says it is still not dispatched, and a refusal is shown", async ({ page }) => {
  await asLiveDrafts(page);
  let refuse = true;
  await page.route("**/api/dashboard/drafts/*/decide*", async (r) => {
    if (refuse) { refuse = false; return r.fulfill({ status: 409, json: { error: { code: "NOT_ALLOWED", message: "V11 is already held for 2026-10-30" } } }); }
    await r.fulfill({ json: { draft_id: "x", status: "approved", revise_run_id: null } });
  });
  await playS1WithoutLessons(page);
  const card = plan(page);
  await card.getByRole("button", { name: /Approve draft/ }).click();
  await expect(card.getByRole("alert")).toContainText("V11 is already held");
  await card.getByRole("button", { name: /Approve draft/ }).click();
  await expect(card.getByRole("status")).toContainText("Approved by you. It is still not dispatched");
});

test("S4: retiring the rule leaves a card in the chat, and its Undo brings the rule back and ticks the step", async ({ page }) => {
  // Live mode is off in the tests. S4's first and third steps call no model, so the session is shown as live-capable.
  await page.route("**/api/session", async (r) => {
    const body = await (await r.fetch()).json();
    body.models["Muse Spark 1.3"] = { available: true, reason: null };
    body.live_runs_left = 8;
    await r.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start S4", exact: true }).click();
  const guide = page.getByRole("region", { name: /Scenario S4/ });
  await guide.getByRole("button", { name: "Retire the 22 ft gate rule" }).click();
  const card = page.getByRole("region", { name: "You retired a lesson" });
  await expect(card).toContainText("L-T01-002");
  await expect(card).toContainText("Only your own copy changed.");
  // Step 2 is live; skip ahead the way a visitor might: Undo on the card.
  await card.getByRole("button", { name: "Undo: bring back L-T01-002" }).click();
  await expect(page.getByRole("region", { name: "You brought a lesson back" })).toContainText("It is active again");
  await expect(guide.getByLabel("Step 3 done")).toBeVisible();
  await expect(page.getByRole("list", { name: "Closed loop" }).locator("li.lit")).toHaveCount(1); // Approve
  await page.goto("/#learning/L-T01-002");
  await expect(page.getByRole("article", { name: "Lesson L-T01-002" })).toContainText("Active rule: code enforces it");
});

test("the first screen fits a 1280×720 laptop: the problem, what it is built on, and the first scenarios' Start buttons", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/");
  await expect(page.getByRole("list", { name: "Built on Meta Muse" })).toContainText("Spark Open");
  await expect(page.getByRole("heading", { name: "Try it", exact: true })).toBeVisible();
  for (const id of ["S1", "S2", "S3"]) {
    const b = await page.getByRole("button", { name: `Start ${id}`, exact: true }).boundingBox();
    const log = await page.locator(".chat-log").boundingBox();
    expect(b!.y + b!.height).toBeLessThanOrEqual(log!.y + log!.height);
  }
  // On a short screen the impact line and its source move under "Read more".
  await page.getByText("Read more").click();
  await expect(page.getByRole("link", { name: "Redseer, Dec 2024" })).toBeVisible();
});

test("the plan card, its scale and the S1 finish pass the accessibility check", async ({ page }) => {
  const guide = await playS1WithoutLessons(page);
  await guide.getByRole("button", { name: "See what it learned" }).click();
  await guide.getByRole("button", { name: "Undo and redo the approval yourself" }).click();
  await guide.getByRole("button", { name: "Play the same request with lessons" }).click();
  await expect(guide.getByRole("figure")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});
