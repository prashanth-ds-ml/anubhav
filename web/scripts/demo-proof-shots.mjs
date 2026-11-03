// Screenshots of the recorded pages for docs/Demo_Script.md (sections 5–7). Spends nothing: run it against a keyless server.
//   ANUBHAV_PUBLIC=1 meta_api= baseten_api_key= uv run uvicorn anubhav.api.app:app --port 7871     (repo root)
//   node scripts/demo-proof-shots.mjs [base-url]                                                  (from web/)
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";

const BASE = process.argv[2] ?? "http://127.0.0.1:7871/";
const OUT = new URL("../../docs/demo_screens/", import.meta.url);
const SHOTS = [
  ["5-1-kazipet", "#learning/L-T01-011", "What it has learned"],
  ["6-1-runs", "#runs", "Runs you can inspect"],
  ["6-2-tools", "#tools", "Repeated questions that could become tools"],
  ["7-1-claims", "#proof/claims", "Not measured yet"],
  ["7-2-benchmarks", "#proof/bench", "Every experiment we pre-registered, including the ones that failed"],
  ["7-3-agents", "#agents", "Each agent has its own way to learn"],
];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
for (const [name, hash, heading] of SHOTS) {
  await p.goto(BASE + hash);
  await p.getByRole("heading", { name: heading }).first().waitFor({ timeout: 60_000 });
  await p.waitForTimeout(1500);   // charts and lists that load after the heading
  await p.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, { timeout: 120_000 }).catch(() => console.log("  still loading:", name));
  const lesson = hash.match(/learning\/(L-[\w-]+)/);
  if (lesson) {
    const a = p.getByRole("article", { name: `Lesson ${lesson[1]}` });
    await a.waitFor({ timeout: 30_000 });
    await a.evaluate((e) => e.scrollIntoView({ block: "start" }));
    await p.waitForTimeout(1500);
  }
  await p.mouse.move(2, 2);
  await p.screenshot({ path: fileURLToPath(new URL(`${name}.png`, OUT)) });
  console.log("saved", name);
}
console.log("page errors:", errors.length ? errors : "none");
await b.close();
