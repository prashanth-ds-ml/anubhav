import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 5: Runs (every step by agent, the work per agent, a mistake and its fix), Agents (how each learns and what is
// measured, read from the result files) and Tools (the benchmark beside the candidate, before and after beside Approve).

const axeClean = async (page: Page) => {
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
};

test("the S2 team run shows the Planner handing off to Tool Forge, with 2 and 4 calls and each one's own cost", async ({ page }) => {
  await page.goto("/#runs");
  await expect(page.getByRole("heading", { name: "Runs you can inspect" })).toBeVisible();
  const open = page.getByRole("button", { name: /^Busiest weekday, as a team/ });
  await open.click();                                          // one list, newest first: the team run is chosen from it
  await expect(open).toHaveAttribute("aria-current", "true");
  const lanes = page.getByRole("region", { name: "Every step, one lane per agent, in time order" });
  await expect(lanes.getByRole("group", { name: "Planner: 2 tool calls" })).toBeVisible();
  await expect(lanes.getByRole("group", { name: "Tool Forge, asked by Planner: 4 tool calls" })).toBeVisible();
  await expect(lanes.getByRole("button", { name: /delegate hands off to Tool Forge/ })).toBeVisible();
  const work = page.getByRole("region", { name: "Work per agent in this run" });
  await expect(work).toContainText("2 calls · $0.030");
  await expect(work).toContainText("4 calls · $0.080");
  await expect(work).toContainText("Analyst and Lesson Miner were not needed.");
  // Choosing a step shows what it sent and the answer it got.
  await lanes.getByRole("button", { name: /Step 3: describe_tables/ }).click();
  const step = page.getByRole("region", { name: "The chosen step" });
  await expect(step).toContainText("Tool Forge · describe_tables");
  await expect(page.getByRole("link", { name: "Raw record (JSON)" })).toHaveAttribute("href", /\/api\/runs\/.+/);
});

test("a real mistake and its fix: the SQL error the database gave, and the agent's corrected call", async ({ page }) => {
  await page.goto("/#runs");
  await page.getByRole("button", { name: /^Busiest weekday, before the tool/ }).click();
  await expect(page).toHaveURL(/#runs\/[0-9a-f]+$/);
  const fix = page.getByRole("region", { name: "A real mistake, fixed by the agent itself" });
  await expect(fix).toContainText("Step 4 · run_query ✕ failed");
  await expect(fix).toContainText("SQL error: no such column: delivery_date");
  await expect(fix).toContainText("t.delivery_date");
  await expect(fix).toContainText("Step 5 · run_query ✓ corrected");
  await expect(fix).toContainText("sh.delivery_date");
  const lanes = page.getByRole("region", { name: "Every step, one lane per agent, in time order" });
  await expect(lanes.getByRole("button", { name: /Step 4: run_query ✕ failed/ })).toHaveAttribute("aria-pressed", "true"); // it opens on the mistake
  await expect(lanes.getByRole("button", { name: /Step 5: run_query .*✓ fixed/ })).toBeVisible();
  // The address opens the same run directly.
  const url = page.url();
  await page.goto("about:blank");
  await page.goto(url);
  await expect(page.getByRole("button", { name: /^Busiest weekday, before the tool/ })).toHaveAttribute("aria-current", "true");
});

test("the Agents page reads its numbers from the result files, and says what is not measured yet", async ({ page }) => {
  const proof = await (await page.request.get("/api/proof")).json();
  const by = Object.fromEntries(proof.map((p: { id: string }) => [p.id, p]));
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  await page.goto("/#agents");
  const team = page.getByLabel("The team, EXP-013");
  const d = by["EXP-013"].decision;
  await expect(team).toContainText(`Right agent chosen: ${pct(d.M0.routing)} → ${pct(d.M1.routing)}`);
  await expect(team).toContainText(`Correct answers: ${d.M0.ok} → ${d.M1.ok} of ${d.M1.n}, not improved`);
  await expect(team).toContainText(`One Planner alone: ${d.S.ok} of ${d.S.n}. The team is not more accurate.`);
  const forge = page.getByRole("article", { name: "Tool Forge" });
  await expect(forge).toContainText(`Learned tool used: ${by["EXP-012b"].decision.learned_tool_used_in.replace("/", " of ")} questions`);
  await expect(forge).toContainText(`Tool calls: ${by["EXP-012b"].arms.Q.mean_tool_calls} → ${by["EXP-012b"].arms.T.mean_tool_calls}`);
  await expect(forge).toContainText("Bar not met");
  await expect(page.getByRole("article", { name: "Lesson Miner" })).toContainText(`Precision ${pct(by["EXP-009b"].pooled.precision)}`);
  // EXP-014 (Muse Spark 1.3), read from /api/proof/curve: the team stage by stage, and each agent before and after.
  const curve = await (await page.request.get("/api/proof/curve")).json();
  const first = curve.stages[0], last = curve.stages[curve.stages.length - 1];
  const r = (x: number) => `${Math.round(x * 1000) / 10}%`;
  await expect(page.getByRole("article", { name: "Analyst" })).toContainText("Muse Spark 1.3 EXP-014: 78% → 78%");
  await expect(page.getByRole("article", { name: "Tool Forge" })).toContainText("Muse Spark 1.3 EXP-016: no tool was made");
  const curveBox = page.getByRole("region", { name: /Does the whole team improve/ });
  await expect(curveBox).toContainText(`The whole team got better as each kind of learning was added: ${r(first.rate)} → ${r(last.rate)}`);
  await expect(curveBox.getByRole("list", { name: "The rules fixed in advance" })).toContainText("Tools: made, used on half the gap questions, cheaper: not met");
  await expect(curveBox.getByRole("list", { name: "Each agent, first version against its final one" })).toContainText("-50 points");
  await expect(page.getByRole("article", { name: "Planner" })).toContainText("Muse Spark 1.3 the live model (EXP-015): 45% → 90%");
});

test("Tools: the benchmark beside the candidates, and what approving changes beside Approve", async ({ page }) => {
  await page.goto("/#tools");
  const bench = page.getByRole("region", { name: "Across the benchmark" });
  await expect(bench).toContainText("14 of 16");
  await expect(bench).toContainText("✕ Bar not met");
  await expect(bench).toContainText("Answers were not worse (94% against 88%)");
  await page.getByRole("article").filter({ hasText: "Threshold reached." }).first().getByRole("button", { name: "Check this query" }).click();
  const checked = page.locator("article.story");
  await expect(checked.getByRole("button", { name: "Approve as a tool" })).toBeVisible();
  const changes = checked.getByRole("complementary", { name: "What approving changes, from recorded runs" });
  await expect(changes).toContainText("Tool calls for the same question");
  await expect(changes).toContainText("Cost of the question");
});

test("Runs, Agents and Tools pass the accessibility check", async ({ page }) => {
  await page.goto("/#runs");
  await expect(page.getByRole("region", { name: "Work per agent in this run" })).toBeVisible();
  await axeClean(page);
  await page.goto("/#agents");
  await expect(page.getByLabel("The team, EXP-013")).toBeVisible();
  await axeClean(page);
  await page.goto("/#tools");
  await expect(page.getByRole("region", { name: "Across the benchmark" })).toBeVisible();
  await axeClean(page);
});
