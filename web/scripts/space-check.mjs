// Checks the hosted Space inside the huggingface.co page (a cross-site iframe, where the visitor cookie is dropped).
// Calls no model: it reads the workspace, flips the workspace switch and reads the picker.
//   node scripts/space-check.mjs [space-page-url] [out-dir]
import { chromium } from "@playwright/test";

const PAGE = process.argv[2] ?? "https://huggingface.co/spaces/KPrashanth/anubhav";
const OUT = process.argv[3];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
await p.goto(PAGE, { waitUntil: "domcontentloaded" });
await p.waitForSelector("iframe", { timeout: 90_000 });
let f;
for (let i = 0; i < 60 && !f; i++) { f = p.frames().find((x) => x.url().includes("hf.space")); if (!f) await p.waitForTimeout(1000); }
if (!f) throw new Error("no app frame");
await f.getByRole("heading", { name: "Try it", exact: true }).waitFor({ timeout: 120_000 });
const sw = f.getByRole("group", { name: "Workspace" });
await sw.waitFor();
const say = async (k) => console.log(k, "|", (await sw.innerText()).replace(/\s+/g, " "),
  "| zero pressed:", await sw.getByRole("button", { name: "Fresh start" }).getAttribute("aria-pressed"));
await say("on open");
const pick = f.getByRole("combobox", { name: "Model for live runs" });
console.log("model picker:", (await pick.count()) ? await pick.inputValue() : "absent",
  "| options:", (await pick.locator("option").allInnerTexts()).join(", "));
console.log("badge:", (await f.locator(".live-badge").innerText().catch(() => "none")).trim());
await sw.getByRole("button", { name: "After learning" }).click();
await f.waitForTimeout(2500);
await say("after switching to recorded");
// the same visitor on the next requests: Learning should list the recorded lessons
await f.evaluate(() => { location.hash = "#learning/L-T01-002"; });
await f.getByRole("article", { name: "Lesson L-T01-002" }).waitFor({ timeout: 60_000 });
console.log("lesson shows:", (await f.getByRole("article", { name: "Lesson L-T01-002" }).locator("p").first().innerText()).trim());
await sw.getByRole("button", { name: "Fresh start" }).click();
await f.waitForTimeout(2500);
await say("after switching back to zero");
if (OUT) await p.screenshot({ path: `${OUT}/space-frame.png` });
const bg = await f.evaluate(() => getComputedStyle(document.body).backgroundColor);
console.log("background:", bg, "| theme button:", await f.getByRole("button", { name: /theme/i }).count());
console.log("page errors:", errors.length ? errors : "none");
await b.close();
