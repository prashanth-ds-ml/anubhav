import { test, expect, type Page } from "@playwright/test";

// Nov 4: a draft made by create_dispatch_drafts arrived with order_ids and no orders, the drafts panel read
// orders.length, and the whole page went blank. Here every main page is served thin or odd answers (fields missing,
// null, empty lists, unknown ids, that draft shape, a run with nothing in it, a lesson nobody mined) and must still
// show its header, its tabs and either its content or a readable fallback, with no script error and no part failing.

test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

/** The draft exactly as create_dispatch_drafts returns one: order_ids, no orders, no delivery date, a spot-hire truck. */
const SEVERAL_TOOL_DRAFT = { vehicle_id: "SPOT-HIRE-9", order_ids: ["O-1001", "O-1002"], ok: true, draft_id: "DR-ODD001", load: { kg: 900 } };

const THIN: [RegExp, unknown][] = [
  [/\/api\/session(\?|$)/, { public: true, default_mode: "replay" }],                       // no models, caps, voice or runs left
  [/\/api\/companies(\?|$)/, [{ company: "T01" }]],
  [/\/api\/suggestions\?/, {}],                                                                // not even a list
  [/\/api\/fresh\/status\?/, { fresh: false }],                                                 // no counts, no agent versions
  [/\/api\/dashboard\/orders\?/, { orders: null }],
  [/\/api\/dashboard\/fleet\?/, { vehicles: [{ vehicle_id: "V-01" }] }],                        // a truck with no length or payload
  [/\/api\/dashboard\/drafts\?/, { drafts: [
    { ...SEVERAL_TOOL_DRAFT, status: "draft", source: "live", run_id: null },
    { draft_id: "DR-ODD002", status: "rejected", vehicle_id: null, delivery_date: null, orders: null, warnings: null, why: {} },
    { draft_id: "DR-ODD003", status: "cancelled", vehicle_id: "V-01", load: null, stops: { stops: null }, decisions: null, why: { lessons: [null], checks: [null] } },
  ] }],
  [/\/api\/dashboard\/company\?/, { company: "T01" }],                                         // no facts, no written rules
  [/\/api\/ledger\?/, [{ run_id: "x", seq: 0, agent_id: "planner", type: "something_new", payload: null },
    { run_id: "x", seq: 1, agent_id: "planner", type: "lesson_used", payload: {} },
    { run_id: "x", seq: 2, agent_id: "planner", type: "draft_created", payload: { draft_id: "DR-ODD001" } }]],
  [/\/api\/learning\/lessons\?/, [
    { lesson_id: "L-T01-002", kind: "site_access", state: "CANDIDATE", what: "a gate rule", miner: null, gate: null, params: { site_id: "C9", max_length_ft: 22 } },
    { lesson_id: "L-T01-009", kind: "a_kind_from_later", state: null, claim: "odd", miner: { evidence: "not a list" } },
  ]],
  [/\/api\/learning\/lessons\/L-T01-002\/evidence\?/, { kind: "trips", lesson_kind: "site_access" }],   // no rows, site or window
  [/\/api\/learning\/lessons\/L-T01-009\/evidence\?/, { kind: "closure", lesson_kind: "closure" }],
  [/\/api\/learning\/timeline\?/, [{ kind: "lesson" }]],
  [/\/api\/compare\?/, { request: null, cold: { run_id: "a" }, with_lessons: { run_id: "b", drafts: [SEVERAL_TOOL_DRAFT] }, with_learned_tools: null,
    pairs: [{ request: "x", before: null, after: { run_id: "c" } }] }],
  [/\/api\/tools\?/, [{ tool_id: "T01-tool-11111111", status: "candidate" },
    { tool_id: "T01-tool-22222222", name: "busiest", status: "active", checks: { health: { ok: false } } },
    { tool_id: "T01-tool-33333333", name: "broken", status: "candidate", description: null, checks: { pass: false, repair: { by: "tool_forge" } } }]],
  [/\/api\/tools\/candidates\?/, [{ key: "abcdef0123" }]],
  [/\/api\/agents\?/, [{ agent: "planner", name: "Planner" }, { agent: "an_agent_from_later" }]],
  [/\/api\/logs\/agents\?/, [{ agent: "planner", runs: 2 }]],
  [/\/api\/logs\/runs\?/, [{ run_id: "r-empty" }]],
  [/\/api\/runs\/r-empty\/steps/, { run_id: "r-empty" }],                                        // no events, agents or fixes
  [/\/api\/proof$/, [{ id: "EXP-012b", arms: {} }, { id: "EXP-004", arms: { tools: 3 } }, { id: "EXP-013", decision: { S: {}, M0: {}, M1: {} } },
    { id: "EXP-011R", summary: { "T01:B": {}, "T01:C": { by_family: { real_capacity: 3 } } }, pooled: {}, repeats: [{}] }, { id: "EXP-009b", pooled: {} }, null]],
  [/\/api\/proof\/registry$/, { experiments: [{ id: "EXP-001", verdict: "something_new" }, { id: "EXP-014", verdict: "not_run", plan: {} }, null] }],
  [/\/api\/proof\/curve$/, { measured: true, agents: { planner: {} } }],
];

/** Serve the thin answers; anything else goes to the real server. Collects script errors and parts that failed to draw. */
async function thin(page: Page, extra: [RegExp, unknown][] = []) {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && /could not be shown/.test(m.text())) problems.push(`boundary: ${m.text()}`); });
  for (const [re, json] of [...THIN, ...extra]) await page.route(re, (r) => r.fulfill({ json }));
  return problems;
}

async function shellIsUp(page: Page, problems: string[]) {
  await expect(page.getByRole("heading", { level: 1, name: "Anubhav" })).toBeVisible();
  await expect(page.getByRole("tablist", { name: "Main" })).toBeVisible();
  await expect(page.getByText(/could not be shown/)).toHaveCount(0);
  expect(problems).toEqual([]);
}

const PAGES: [string, (page: Page) => Promise<void>][] = [
  ["#", async (page) => {
    await expect(page.getByRole("region", { name: "Agent chat" })).toBeVisible();
    await expect(page.getByRole("tabpanel")).toContainText("No orders to show");
  }],
  ["#plans", async (page) => {
    const odd = page.getByRole("article", { name: /Draft DR-ODD001/ });
    await expect(odd).toContainText("O-1001, O-1002");                        // order_ids read as its orders
    await expect(odd).toContainText("SPOT-HIRE-9");                           // a truck not in the fleet still shows its id
    await expect(page.getByRole("article", { name: /Draft DR-ODD002/ })).toBeVisible();
    await expect(page.getByRole("article", { name: /Draft DR-ODD003/ })).toBeVisible();
  }],
  ["#fleet", async (page) => { await expect(page.getByRole("tabpanel")).toContainText("V-01"); }],
  ["#company", async (page) => { await expect(page.getByRole("tabpanel")).toContainText("Written rules (0)"); }],
  ["#ledger", async (page) => { await expect(page.getByRole("tabpanel")).toContainText("something new"); }],
  ["#learning", async (page) => {
    await expect(page.getByRole("navigation", { name: "Lessons" })).toContainText("L-T01-009");
    await expect(page.getByRole("article", { name: /^Lesson / })).toBeVisible();
  }],
  ["#learning/L-T01-002", async (page) => {
    const art = page.getByRole("article", { name: "Lesson L-T01-002" });
    await expect(art).toContainText("Not mined by a model here");             // miner: null
    await expect(art).toContainText("Evidence check: —");                     // gate: null
    await expect(art).toContainText("No trips to this site in the records."); // evidence with no rows
  }],
  ["#learning/L-T01-009", async (page) => {
    const art = page.getByRole("article", { name: "Lesson L-T01-009" });
    await expect(art).toContainText("No closure delays in the records.");
  }],
  ["#tools", async (page) => {
    await expect(page.getByRole("heading", { name: "Repeated questions that could become tools" })).toBeVisible();
    await expect(page.getByRole("article", { name: "Checked broken" })).toContainText("Checks failed");
    await expect(page.getByRole("article", { name: "Approved busiest" })).toContainText("Needs repair: no reason recorded");
  }],
  ["#agents", async (page) => {
    await expect(page.getByRole("heading", { name: "Each agent has its own way to learn" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Planner" })).toBeVisible();
  }],
  ["#runs", async (page) => {
    await expect(page.getByRole("heading", { name: "Runs you can inspect" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "A run with no recorded request" })).toBeVisible();
    await expect(page.getByText("This run ended without an answer.")).toBeVisible();
  }],
  ["#proof/bench", async (page) => {
    await expect(page.getByRole("heading", { name: /Every experiment we pre-registered/ })).toBeVisible();
    await expect(page.getByRole("list", { name: /experiments/ })).toContainText("EXP-001");
  }],
  ["#proof/claims", async (page) => {
    await expect(page.getByRole("heading", { name: /Check our claims/ })).toBeVisible();
    await expect(page.getByRole("table").first()).toContainText("EXP-014");
  }],
];

for (const [hash, content] of PAGES) {
  test(`${hash} with thin or odd answers keeps the page up and readable`, async ({ page }) => {
    const problems = await thin(page);
    await page.goto(`/${hash}`);
    await content(page);
    await shellIsUp(page, problems);
  });
}

test("a server that sends nothing usable at all: every main tab still opens", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && /could not be shown/.test(m.text())) problems.push(`boundary: ${m.text()}`); });
  await page.route(/\/api\/(?!chat\/stream)/, (r) => r.fulfill({ json: null }));
  for (const hash of ["#", "#plans", "#learning", "#tools", "#agents", "#runs", "#proof/bench", "#proof/claims"]) {
    await page.goto(`/${hash}`);
    await shellIsUp(page, problems);
  }
});

const ev = (run: string, seq: number, type: string, payload: Record<string, unknown>) =>
  `event: ${type}\nid: ${seq}\ndata: ${JSON.stringify({ run_id: run, seq, agent_id: "planner", agent_run_id: run, caller: "", depth: 0, ts: null, type, payload })}\n\n`;

test("a live run whose draft came from create_dispatch_drafts: the plan card and the timeline show its orders", async ({ page }) => {
  const problems = await thin(page, [
    [/\/api\/session(\?|$)/, { public: true, default_mode: "replay", models: { "Muse Spark 1.3": { available: true, reason: null, key: "spark" } },
      caps: { per_session: 8, per_day: 50 }, live_runs_left: 8, voice: { available: false, reason: null } }],
    [/\/api\/chat$/, { run_id: "r-odd", mode: "live" }],
    [/\/api\/dashboard\/drafts\?.*run_id=r-odd/, { drafts: [{ ...SEVERAL_TOOL_DRAFT, status: "draft", source: "live", why: { lessons: null } }], source: "live" }],
  ]);
  await page.route(/\/api\/chat\/stream\?run_id=r-odd/, (r) => r.fulfill({ contentType: "text/event-stream",
    body: ev("r-odd", 0, "agent_start", { model: "muse-spark-1.3" })
      + ev("r-odd", 1, "draft_created", { draft_id: "DR-ODD001", vehicle_id: "SPOT-HIRE-9", orders: null })     // as older stored events have it
      + ev("r-odd", 2, "agent_done", { reply: null, stop: "answered", tool_calls: 1, cost_usd: null, drafts: null })
      + `event: end\ndata: {"stop":"answered","mode":"live"}\n\n` }));
  await page.goto("/");
  await page.getByRole("textbox", { name: /Ask/ }).first().fill("plan both orders");
  await page.getByRole("button", { name: "Send" }).click();
  const card = page.getByRole("article", { name: "Plan DR-ODD001" });
  await expect(card).toContainText("O-1001, O-1002");
  await expect(card).toContainText("SPOT-HIRE-9");
  await expect(page.getByRole("list", { name: "Run events" })).toContainText("Draft DR-ODD001 on SPOT-HIRE-9");
  await shellIsUp(page, problems);
});
