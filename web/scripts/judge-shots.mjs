// Every page as a judge sees it, in both workspaces, for the final review. Calls no model.
//   ANUBHAV_PUBLIC=1 ANUBHAV_START_FRESH=1 uv run uvicorn anubhav.api.app:app --port 7864   (repo root, keys in .env)
//   node scripts/judge-shots.mjs [base-url] [out-dir]
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://127.0.0.1:7864/";
const OUT = process.argv[3] ?? "judge-shots";
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
const PAGES = [["desk", ""], ["plans", "#plans"], ["learning", "#learning"], ["tools", "#tools"], ["agents", "#agents"], ["runs", "#runs"],
  ["proof-bench", "#proof/bench"], ["proof-claims", "#proof/claims"]];
async function shoot(prefix) {
  for (const [name, hash] of PAGES) {
    await p.goto(BASE + hash);
    await p.waitForTimeout(2500);
    await p.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, { timeout: 60_000 }).catch(() => {});
    await p.mouse.move(2, 2);
    await p.screenshot({ path: `${OUT}/${prefix}-${name}.png`, fullPage: true });
    console.log("saved", `${prefix}-${name}`);
  }
}
await p.goto(BASE);
await p.getByRole("group", { name: "Workspace" }).waitFor({ timeout: 90_000 });
await shoot("1-fresh");
await p.getByRole("group", { name: "Workspace" }).getByRole("button", { name: "After learning" }).click();
await p.waitForTimeout(2000);
await shoot("2-learned");
console.log("page errors:", errors.length ? errors : "none");
await b.close();
