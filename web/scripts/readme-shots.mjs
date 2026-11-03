// Screenshots for the README, taken from a running app in replay mode (no keys).
//   ANUBHAV_PUBLIC=1 uv run uvicorn anubhav.api.app:app --port 7861     (from the repo root, after `npm run build` in web/)
//   node scripts/readme-shots.mjs [base-url]                             (from web/)
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";

const BASE = process.argv[2] ?? "http://127.0.0.1:7861/";
const OUT = new URL("../readme-assets/", import.meta.url);
const b = await chromium.launch();
const errors = [];

async function page(width, height, scheme = "light") {
  const p = await b.newPage({ viewport: { width, height }, colorScheme: scheme });
  p.on("pageerror", (e) => errors.push(e.message));
  return p;
}
const save = async (p, name) => { await p.mouse.move(2, 2); await p.waitForTimeout(1500); await p.screenshot({ path: fileURLToPath(new URL(`${name}.png`, OUT)) }); console.log("saved", name); };

// The first screen, and S1 from start to finish.
let p = await page(1440, 900);
await p.goto(BASE);
await p.getByRole("heading", { name: "Try it: seven scenarios" }).waitFor({ timeout: 90_000 });
await save(p, "start");
await p.getByRole("button", { name: "Start S1" }).click();
const g = p.getByRole("region", { name: /Scenario S1/ });
await g.getByRole("button", { name: "Play the request without lessons" }).click();
await p.locator(".plan-card").last().waitFor({ timeout: 90_000 });
await p.locator(".plan-card").last().scrollIntoViewIfNeeded();
await save(p, "s1-without-lessons");
await g.getByRole("button", { name: "See what it learned" }).click();
await g.getByRole("button", { name: "Undo and redo the approval yourself" }).click();
await g.getByRole("button", { name: "Play the same request with lessons" }).click();
await g.getByText(/All 4 steps done/).waitFor({ timeout: 90_000 });
await save(p, "s1-done");

// One screen per main tab.
for (const [name, hash] of [["learning", "#learning/L-T01-002"], ["kazipet", "#learning/L-T01-011"], ["runs", "#runs"], ["agents", "#agents"], ["tools", "#tools"], ["proof", "#proof/bench"], ["claims", "#proof/claims"]]) {
  await p.goto(BASE + hash);
  await p.waitForTimeout(1200);
  await save(p, name);
}

// Dark mode and a phone.
p = await page(1440, 900, "dark");
await p.goto(BASE + "#runs");
await save(p, "runs-dark");
p = await page(390, 844);
await p.goto(BASE);
await save(p, "phone");

console.log("page errors:", errors.length ? errors : "none");
await b.close();
