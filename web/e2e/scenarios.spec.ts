import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The six scenarios a judge can try. Recorded ones replay saved runs; live ones are mocked here (no keys, no credits).

async function home(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Try it: six scenarios" })).toBeVisible();
}

/** Make the real session say Muse Spark 1.3 can run, without any key. */
async function liveOn(page: Page) {
  await page.route("**/api/session", async (r) => {
    const res = await r.fetch();
    const s = await res.json();
    await r.fulfill({ response: res, json: { ...s, models: { ...s.models, "Muse Spark 1.3": { available: true, reason: null } }, live_runs_left: 8 } });
  });
}

test("six scenarios, each saying whether it is recorded or live; without keys the live ones say why and stay closed", async ({ page }) => {
  await home(page);
  const cards = page.locator(".sc-card article");
  await expect(cards).toHaveCount(6);
  for (const id of ["S1", "S2", "S3"]) {
    const c = page.getByRole("article", { name: new RegExp(`^${id} `) });
    await expect(c).toContainText("Recorded · watch it");
    await expect(c).toContainText("free");
    await expect(c.getByRole("button", { name: `Start ${id}` })).toBeEnabled();
  }
  const s6 = page.getByRole("article", { name: /^S6 / });
  await expect(s6).toContainText("Recorded data · explore it");
  await expect(s6).toContainText("free");
  for (const id of ["S4", "S5"]) {
    const c = page.getByRole("article", { name: new RegExp(`^${id} `) });
    await expect(c).toContainText("Live · you run it");
    await expect(c).toContainText(/Live mode is off on this demo/);
    await expect(c.getByRole("button", { name: `Start ${id}` })).toBeDisabled();
  }
  const axe = await new AxeBuilder({ page }).include(".scenarios").analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);
});

test("S1 plays the recorded request without lessons, then with them, and ticks each step", async ({ page }) => {
  await home(page);
  await page.getByRole("button", { name: "Start S1" }).click();
  const guide = page.getByRole("region", { name: /Scenario S1/ });
  await expect(guide).toBeVisible();
  await guide.getByRole("button", { name: "Play the request without lessons" }).click();
  await expect(page.locator(".recorded").last()).toContainText("lessons off");
  await expect(page.locator(".bubble.answer").last()).toContainText("V11", { timeout: 60_000 });
  await expect(guide.getByLabel("Step 1 done")).toBeVisible();
  await guide.getByRole("button", { name: "All steps" }).click();

  await guide.getByRole("button", { name: "See what it learned" }).click();
  await expect(page.getByRole("tab", { name: "Learning", exact: true })).toHaveAttribute("aria-selected", "true");

  await guide.getByRole("button", { name: "Play the same request with lessons" }).click();
  await expect(page.locator(".recorded").last()).toContainText("lessons on");
  await expect(page.locator(".bubble.answer").last()).toContainText("22 ft", { timeout: 60_000 });
  await expect(guide.getByText("Check it yourself")).toBeVisible();
});

test("S3 switches to the new company first", async ({ page }) => {
  await home(page);
  await page.getByRole("button", { name: "Start S3" }).click();
  await page.getByRole("button", { name: "Switch to the new company" }).click();
  await expect(page.getByRole("combobox", { name: "Company" })).toHaveValue("TNEW");
  await page.getByRole("button", { name: "Play the request without shared lessons" }).click();
  await expect(page.locator(".recorded").last()).toContainText("lessons off");
  await expect(page.locator(".bubble.answer").last()).toBeVisible({ timeout: 60_000 });
});

test("S4 retires the rule in this visitor's own store, sends the request live, and brings the rule back", async ({ page }) => {
  await liveOn(page);
  let sent: Record<string, unknown> | null = null;
  // Stand in for the live run: answer with a recorded run, as the server would stream a live one.
  await page.route("**/api/chat", async (r) => {
    sent = r.request().postDataJSON();
    await r.fulfill({ json: { run_id: "fae8975894", mode: "live" } });
  });
  await home(page);
  await page.getByRole("button", { name: "Start S4" }).click();
  const guide = page.getByRole("region", { name: /Scenario S4/ });
  await expect(guide).toContainText("In our own test each step behaved as described once");

  await guide.getByRole("button", { name: "Retire the 22 ft gate rule" }).click();
  await expect(guide.getByRole("status")).toContainText(/Retired L-T01-\d+/);
  const lessons = await (await page.request.get("/api/learning/lessons?company=T01")).json();
  // page.request shares the page's cookie, so this is the same visitor's store
  expect(lessons.find((l: { kind: string }) => l.kind === "site_access").state).toBe("RETIRED");

  await guide.getByRole("button", { name: "Send the request live (live)" }).click();
  await expect.poll(() => sent).toMatchObject({ mode: "live", model: "spark", company: "T01" });
  await expect(page.locator(".recorded.live").last()).toContainText("Live run, just now");

  await guide.getByRole("button", { name: "Bring the rule back" }).click();
  await expect(guide.getByRole("status")).toContainText("is active again");
});

test("with live mode on, a typed request that matches no saved run goes to the model", async ({ page }) => {
  await liveOn(page);
  let sent: Record<string, unknown> | null = null;
  await page.route("**/api/chat", async (r) => {
    sent = r.request().postDataJSON();
    await r.fulfill({ json: { run_id: "fae8975894", mode: "live" } });
  });
  await home(page);
  await expect(page.getByText(/Live: Muse Spark 1.3 answers any request/)).toBeVisible();
  await page.getByLabel("Ask the agents").fill("Khammam orders ki rendu bandlu pettu.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => sent).toMatchObject({ mode: "live", message: "Khammam orders ki rendu bandlu pettu." });
});

// ---- polish (Nov 2): the payoff is on screen, not buried in text
test("a plan card shows the truck and whether it fits the learned gate rule: 32 ft fails, 22 ft fits", async ({ page }) => {
  await home(page);
  await page.getByRole("button", { name: "Start S1" }).click();
  await page.getByRole("button", { name: "Play the request without lessons" }).click();
  const bad = page.locator(".plan-card").last();
  await expect(bad).toContainText("32 ft", { timeout: 60_000 });
  await expect(bad).toContainText("Too long for this gate");
  await expect(bad).toContainText("Lessons were off for this run");
  await expect(page.locator(".bubble.answer").last().locator("ul li").first()).toBeVisible(); // "* " lines are a real list
  await expect(page.locator(".bubble.answer").last()).not.toContainText("* Order");
});

test("a link opens a scenario directly, the stepper shows one step at a time, and the finish shows before and after", async ({ page }) => {
  await page.goto("/?tour=S1");
  const guide = page.getByRole("region", { name: /Scenario S1/ });
  await expect(guide).toBeVisible();
  const next = guide.locator(".sc-step.big");
  await expect(next).toHaveText("Play the request without lessons");
  for (let i = 0; i < 4; i++) {
    await next.click();
    if (i === 0 || i === 3) await expect(page.locator(".plan-card").last()).toBeVisible({ timeout: 60_000 });
  }
  const pair = guide.getByLabel("Before and after");
  await expect(pair).toContainText("32 ft");
  await expect(pair).toContainText("22 ft");
  await expect(pair).toContainText("Too long for the gate");
  await expect(pair).toContainText("Fits the gate");
});

test("S2's approve step ticks only once a tool is approved, and New tools leads with the right candidate", async ({ page }) => {
  await home(page);
  await page.getByRole("button", { name: "Start S2" }).click();
  const guide = page.getByRole("region", { name: /Scenario S2/ });
  await guide.getByRole("button", { name: "Ask the Telugu data question" }).click();
  await guide.getByRole("button", { name: "Check and approve the query as a tool" }).click();
  await expect(page.getByRole("tab", { name: "Tools", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(guide.getByText(/Waiting for you to approve a tool/)).toBeVisible();
  await expect(guide.getByLabel("Step 2 done")).toHaveCount(0);
  const first = page.locator("article[aria-label^='Candidate']").first();
  await expect(first).toContainText("Threshold reached");
  await first.getByRole("button", { name: "Check this query" }).click();
  await page.getByRole("button", { name: "Approve as a tool" }).first().click();
  await expect(guide.getByLabel("Step 2 done")).toBeVisible();
});

test("Proof leads with three headline figures, each linked to its result file", async ({ page }) => {
  await page.goto("/#proof");
  const tiles = page.getByRole("region", { name: "Headline results" }).locator(".tile");
  await expect(tiles).toHaveCount(3);
  await expect(tiles.nth(0)).toContainText("90%");
  await expect(tiles.nth(1)).toContainText("100%");
  await expect(tiles.nth(2).getByRole("link", { name: "Result file" })).toHaveAttribute("href", /exp011r/);
});

test("fleet reasons and agent versions are in plain words", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("combobox", { name: "Company" }).selectOption("TNEW");
  await page.getByRole("tab", { name: "Fleet" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Insurance expired");
  await expect(page.getByRole("tabpanel")).not.toContainText("_until");
  await page.getByRole("tab", { name: "Agents" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Version 1");
});
