import { test, expect, type Page } from "@playwright/test";

// When a run stops for a person (owner, Nov 3): a plain question with Approve, Decline and Other, and the reply continues
// the same run live. The model is mocked; nothing here spends credit.

test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

const ev = (run: string, seq: number, type: string, payload: Record<string, unknown>, depth = 0) =>
  `event: ${type}\nid: ${seq}\ndata: ${JSON.stringify({ run_id: run, seq, agent_id: "planner", agent_run_id: run, caller: "", depth, ts: null, type, payload })}\n\n`;

async function liveRun(page: Page, events: string, stop: string) {
  await page.route("**/api/session", async (r) => {
    try {
      const res = await r.fetch();
      const s = await res.json();
      await r.fulfill({ response: res, json: { ...s, models: { ...s.models, "Muse Spark 1.3": { available: true, reason: null, key: "spark" } }, live_runs_left: 8 } });
    } catch { /* the test ended while this was in flight */ }
  });
  const resumed: string[] = [];
  await page.route(/\/api\/chat$/, (r) => r.fulfill({ json: { run_id: "r1", mode: "live" } }));
  await page.route(/\/api\/runs\/r1\/resume/, (r) => { resumed.push(r.request().postDataJSON().reply); return r.fulfill({ json: { run_id: "r2", mode: "live", resumed_from: "r1" } }); });
  await page.route(/\/api\/chat\/stream\?run_id=r1/, (r) => r.fulfill({ contentType: "text/event-stream", body: events + `event: end\ndata: {"stop":"${stop}","mode":"live"}\n\n` }));
  await page.route(/\/api\/chat\/stream\?run_id=r2/, (r) => r.fulfill({ contentType: "text/event-stream",
    body: ev("r2", 0, "agent_start", { model: "muse-spark-1.3" }) + ev("r2", 1, "agent_done", { reply: "Done after your approval.", stop: "answered", tool_calls: 2 })
      + `event: end\ndata: {"stop":"answered","mode":"live"}\n\n` }));
  await page.goto("/");
  await page.getByRole("textbox", { name: /Plan a truck|Ask/ }).first().fill("ee vaaram motham lo enni tonnulu?");
  await page.getByRole("button", { name: "Send" }).click();
  return resumed;
}

test("a tool refused 3 times: the question says what happened, and Approve continues the same run", async ({ page }) => {
  const stopEvents = ev("r1", 0, "agent_start", { model: "muse-spark-1.3" })
    + ev("r1", 1, "needs_person", { rule: "tool_refused", tool: "get_route_info", last_error: { code: "BAD_ARGS", message: "unknown site" }, question: "x" })
    + ev("r1", 2, "agent_done", { reply: "", stop: "needs_person", tool_calls: 5 });
  const resumed = await liveRun(page, stopEvents, "needs_person");
  const ask = page.getByRole("group", { name: "Waiting for you" });
  await expect(ask).toContainText("It tried get_route_info 3 times and the system refused each time (last: unknown site)");
  await expect(ask.getByRole("button", { name: "Decline" })).toBeEnabled();
  await ask.getByRole("button", { name: "Approve: try again" }).click();
  await expect(page.getByText("Done after your approval.")).toBeVisible();
  expect(resumed).toHaveLength(1);
  expect(resumed[0]).toMatch(/^Approved: try again/);
  await expect(ask).toContainText("You chose: Approve");
});

test("the budget used up: it answers with what it has, then asks to continue; Other sends your own instructions", async ({ page }) => {
  const stopEvents = ev("r1", 0, "agent_start", { model: "muse-spark-1.3" })
    + ev("r1", 1, "agent_done", { reply: "Distances for 12 of 15 sites so far.", stop: "limit", tool_calls: 12 });
  const resumed = await liveRun(page, stopEvents, "limit");
  await expect(page.getByText("Distances for 12 of 15 sites so far.")).toBeVisible();
  const ask = page.getByRole("group", { name: "Waiting for you" });
  await expect(ask).toContainText("It made 12 tool calls, the most one request may make");
  await ask.getByRole("button", { name: "Other…" }).click();
  await ask.getByLabel("What should it do next?").fill("Hand the totals to tool_forge as one query.");
  await ask.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Done after your approval.")).toBeVisible();
  expect(resumed).toEqual(["Hand the totals to tool_forge as one query."]);
});

test("Decline at the budget limit spends nothing", async ({ page }) => {
  const stopEvents = ev("r1", 0, "agent_start", { model: "muse-spark-1.3" }) + ev("r1", 1, "agent_done", { reply: "Partial.", stop: "limit", tool_calls: 12 });
  const resumed = await liveRun(page, stopEvents, "limit");
  const ask = page.getByRole("group", { name: "Waiting for you" });
  await ask.getByRole("button", { name: "Decline" }).click();
  await expect(ask).toContainText("You chose: Decline");
  expect(resumed).toEqual([]);
});
