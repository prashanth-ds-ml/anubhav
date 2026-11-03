// One real run of "Start from nothing" (S0) on a live-capable local server, with screenshots for docs/Demo_Script.md.
// Spends real Meta API credit (≈ $0.20): two live questions and one learning run. Start the server first:
//   ANUBHAV_PUBLIC=1 baseten_api_key= uv run uvicorn anubhav.api.app:app --port 7862      (repo root, Meta key in .env)
//   node scripts/demo-fresh-run.mjs [base-url]                                          (from web/)
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://127.0.0.1:7862/";
const OUT = new URL("../../docs/demo_screens/", import.meta.url);
mkdirSync(fileURLToPath(OUT), { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
const shot = async (name) => { await p.mouse.move(2, 2); await p.waitForTimeout(800); await p.screenshot({ path: fileURLToPath(new URL(`${name}.png`, OUT)) }); console.log("saved", name); };
const t0 = Date.now();
const at = () => `${Math.round((Date.now() - t0) / 1000)}s`;

await p.goto(BASE);
await p.getByRole("heading", { name: "Try it: seven scenarios" }).waitFor({ timeout: 90_000 });
await shot("1-first-screen");
await p.getByRole("button", { name: "Start S0" }).click();
const g = p.getByRole("region", { name: /Scenario S0/ });
await g.getByRole("button", { name: "Start fresh" }).click();
await g.getByRole("status").filter({ hasText: "Started fresh" }).waitFor();
console.log(at(), "fresh:", await g.getByRole("status").filter({ hasText: "Started fresh" }).innerText());
await shot("2-1-started-fresh");

await g.getByRole("button", { name: /Ask for a truck/ }).click();
await p.locator(".plan-card").last().waitFor({ timeout: 240_000 });
await p.locator(".plan-card .plan-size").last().filter({ hasText: /ft/ }).waitFor({ timeout: 20_000 });
await g.getByRole("button", { name: /Learn from the records/ }).waitFor({ timeout: 120_000 });   // the step ticks when the run ends
const first = (await p.locator(".plan-card .plan-size").allTextContents()).join(" | ");
console.log(at(), "first answer:", first);
await p.locator(".chat-log").evaluate((e) => e.scrollTo(0, 0));
await shot("2-3-run-with-tool-calls");
await p.locator(".plan-card").last().scrollIntoViewIfNeeded();
await shot("2-4-plan-card");

await g.getByRole("button", { name: /Learn from the records/ }).click();
const panel = p.getByRole("region", { name: "Learn from the records" });
await panel.getByRole("button", { name: /Learn from the records/ }).click();
await panel.getByRole("list", { name: "What it proposed, with the gate's verdict" }).waitFor({ timeout: 240_000 });
console.log(at(), "learned:", (await panel.getByRole("list", { name: "Learning, step by step" }).innerText()).replace(/\s+/g, " "));
for (const li of await panel.getByRole("listitem").filter({ has: p.locator(".learned-what") }).all()) console.log("   -", (await li.innerText()).replace(/\s+/g, " "));
await panel.scrollIntoViewIfNeeded();
await shot("3-1-learned-from-records");

// Approve the gate rule as a rule (enforced by code), or as advice if the gate didn't mark it enforceable.
const row = p.getByRole("button", { name: /^L-T01-\d+ .*no truck longer than 22 ft/ }).first();
await row.click();
const id = (await row.innerText()).split(/\s/)[0];
const asRule = p.getByRole("button", { name: `Approve as a rule…, ${id}` });
if (await asRule.count()) {
  await asRule.click();
  await p.getByLabel(/What did you verify/).fill("Checked the evidence: three trucks over 22 ft were turned back at this gate.");
  await p.getByRole("button", { name: "Approve as a rule" }).click();
} else {
  await p.getByRole("button", { name: `Approve as advice, ${id}` }).click();
}
await p.getByRole("article", { name: `Lesson ${id}` }).getByText(/Active (rule|advice)/).waitFor();
console.log(at(), "approved", id);
await shot("3-2-gate-lesson-approved");

await g.getByRole("button", { name: /Ask again/ }).waitFor({ timeout: 60_000 });   // ticks once the rule is active
await g.getByRole("button", { name: /Ask again/ }).click();
await p.locator(".plan-card").nth(1).waitFor({ timeout: 240_000 });
await p.locator(".plan-card .plan-size").nth(1).filter({ hasText: /ft/ }).waitFor({ timeout: 20_000 });
await g.getByText(/All 5 steps done|Done\./).first().waitFor({ timeout: 180_000 });
console.log(at(), "second answer:", (await p.locator(".plan-card .plan-size").allTextContents()).join(" | "));
await p.locator(".plan-card").last().scrollIntoViewIfNeeded();
await shot("4-1-same-question-right");
console.log("page errors:", errors.length ? errors : "none");
await b.close();
