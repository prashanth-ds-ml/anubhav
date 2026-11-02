import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A repeated question can become a tool, but only after its checks pass and a person approves.
// Each test is a new visitor, so it starts with the candidate unapproved.
const NAME = "wnum_weekday_by_town";

async function openTools(page: Page) {
  await page.goto("/");
  await page.getByRole("tab", { name: "Tools", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Repeated questions that could become tools" })).toBeVisible();
}

test("a new visitor gets one workspace, not one per request, so an early approval cannot land in a different one", async ({ page }) => {
  const made: string[] = [];
  page.on("response", async (r) => {
    if (!r.url().includes("/api/")) return;
    const c = await r.headerValue("set-cookie").catch(() => null);
    if (c) made.push(`${new URL(r.url()).pathname}: ${c.split(";")[0]}`);
  });
  await openTools(page);
  await expect(page.getByRole("article", { name: `Candidate ${NAME}` })).toBeVisible();
  expect(made, "every workspace the server created for this one visitor").toHaveLength(1);
});

test("a person checks a repeated question, approves it as a tool, and the same question then takes one call", async ({ page }) => {
  await openTools(page);
  const candidate = page.getByRole("article", { name: `Candidate ${NAME}` });
  await expect(candidate).toContainText("Threshold reached");
  await candidate.getByRole("button", { name: "Check this query" }).click();

  const checked = page.getByRole("article", { name: `Checked ${NAME}` });
  await expect(checked.getByText("Checks passed")).toBeVisible();
  await expect(checked.getByRole("list", { name: "Check results" })).toContainText(/Same answers as the (\d+) questions it came from: \1 of \1/);
  await expect(checked.getByRole("list", { name: "Check results" })).toContainText(/Works on (\d+) values it never saw .*: \1 of \1/);
  // Nothing is a tool yet: the before-and-after only appears once a person has approved.
  await expect(page.getByRole("region", { name: "Before and after the tool" })).toHaveCount(0);

  await checked.getByRole("button", { name: "Approve as a tool" }).click();
  const approved = page.getByRole("article", { name: `Approved ${NAME}` });
  await expect(approved.getByText("Active: the agent can call it")).toBeVisible();

  const compare = page.getByRole("region", { name: "Before and after the tool" });
  await expect(compare).toContainText("5 tool calls");
  await expect(compare).toContainText("1 tool call · $0.016");
  await expect(compare).toContainText("Saturday");

  await approved.getByRole("button", { name: "Ask the question again" }).click();
  const answer = page.locator(".bubble.answer");
  await expect(answer).toContainText("Saturday");
  await expect(page.locator(".recorded")).toContainText("Recorded run");
  // The recorded run used the learned tool once, and says so in its own closing step.
  await expect(page.locator(".card", { hasText: /Done \(answered\)/ })).toContainText("1 tool call · $0.016");
  await expect(page.locator(".card.step", { hasText: "busiest_weekday_in_town" })).toHaveCount(1);

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target.join(" ")} ${n.html.slice(0, 90)}`).join(" | ")}`)).toEqual([]);
});

test("a person can decline a checked tool, and it is listed as not in use", async ({ page }) => {
  await openTools(page);
  await page.getByRole("article", { name: `Candidate ${NAME}` }).getByRole("button", { name: "Check this query" }).click();
  const checked = page.getByRole("article", { name: `Checked ${NAME}` });
  await checked.getByRole("button", { name: "Don't approve" }).click();
  await expect(page.getByRole("article", { name: `Approved ${NAME}` })).toHaveCount(0);
  await expect(page.getByText("Not in use (1)")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask the question again" })).toHaveCount(0);
});

test("an approved tool can be retired", async ({ page }) => {
  await openTools(page);
  await page.getByRole("article", { name: `Candidate ${NAME}` }).getByRole("button", { name: "Check this query" }).click();
  await page.getByRole("article", { name: `Checked ${NAME}` }).getByRole("button", { name: "Approve as a tool" }).click();
  const approved = page.getByRole("article", { name: `Approved ${NAME}` });
  await approved.getByRole("button", { name: "Retire" }).click();
  await expect(approved).toHaveCount(0);
  await expect(page.getByText("Not in use (1)")).toBeVisible();
});

test("a tool that fails its checks cannot be approved, and the reasons are shown", async ({ page }) => {
  const failing = {
    tool_id: "NT-T01-failcase", name: "broken_tool", description: "A query that did not hold up.", status: "candidate", params: [],
    checks: {
      pass: false,
      same_rows: [{ request: "q", rows: 7, same: false }],
      held_out: [{ values: { town: "Kazipet" }, ok: false, rows: 0 }],
      reasons: ["It returned different rows from the original run."],
    },
  };
  let checked = false;
  await page.route("**/api/tools/candidates/*/check*", (r) => { checked = true; return r.fulfill({ json: failing }); });
  await page.route(/\/api\/tools\?/, (r) => r.fulfill({ json: checked ? [failing] : [] }));
  await openTools(page);
  await page.getByRole("article", { name: `Candidate ${NAME}` }).getByRole("button", { name: "Check this query" }).click();
  const card = page.getByRole("article", { name: "Checked broken_tool" });
  await expect(card.getByText("Checks failed")).toBeVisible();
  await expect(card).toContainText("It returned different rows from the original run.");
  await expect(card).toContainText("Same answers as the 1 questions it came from: 0 of 1");
  await expect(card.getByRole("button", { name: "Approve as a tool" })).toBeDisabled();
});

test("when the server refuses, the person is told why and nothing changes", async ({ page }) => {
  await page.route("**/api/tools/candidates/*/check*", (r) =>
    r.fulfill({ status: 403, json: { error: { code: "LIVE_OFF", message: "This action is not available on the public demo." } } }));
  await openTools(page);
  const candidate = page.getByRole("article", { name: `Candidate ${NAME}` });
  await candidate.getByRole("button", { name: "Check this query" }).click();
  await expect(page.getByRole("alert")).toContainText("This action is not available on the public demo.");
  await expect(candidate).toBeVisible();
  await expect(candidate.getByRole("button", { name: "Check this query" })).toBeEnabled();
});
