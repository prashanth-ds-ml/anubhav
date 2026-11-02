import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" })).newPage();
await p.goto("http://localhost:7860/");
await p.locator(".starter").first().waitFor({ timeout: 30000 });
const views = {};
views["first view"] = await p.evaluate(() => document.body.innerText);
for (const s of [0, 1, 2]) {
  await p.goto("http://localhost:7860/");
  await p.locator(".starter").nth(s).click();
  await p.locator(".bubble.answer").waitFor({ timeout: 30000 });
  views[`run ${s + 1}`] = await p.locator(".chat").innerText();
}
for (const [slug, name] of [["orders","Orders"],["plans","Route plans and drafts"],["fleet","Fleet"],["company","Company"],["ledger","Ledger"],["agents","Agents"],["learning","Learning"],["proof","Proof"]]) {
  await p.goto(`http://localhost:7860/#${slug}`);
  await p.waitForTimeout(500);
  views[`tab ${name}`] = await p.getByRole("tabpanel").innerText();
}
const all = Object.values(views).join("\n");
const terms = {
  "Meta / Muse / Spark (as model names)": /\b(Meta|Muse|Spark Open|Spark 1\.3|Voice Transcribe)\b/gi,
  "hackathon": /hackathon/gi,
  "synthetic / fictional data": /synthetic|fictional|generated data/gi,
  "unwritten (rule)": /unwritten/gi,
  "the 32 ft / narrow-lane example": /32\s?ft|narrow lane|godown lane/gi,
  "planning time (1-1.5 h, re-plans)": /1[–-]1\.5|re-?plan|hours? per plan/gi,
  "who it is for (dispatcher/planner/small operators)": /dispatcher|planner at|small (transport|operator|distributor)|operators/gi,
  "India / Telugu / Warangal context": /India|Warangal|Telugu/gi,
  "domain pack / sharing with new company": /domain pack|new company|day[- ]1|shared/gi,
  "approve (a lesson) action": /approve/gi,
  "benchmark results (48% / 90% / 33% / 100%)": /48%|90%|33%|100%|EXP-0/gi,
  "open weights": /open[- ]weights/gi,
};
for (const [k, re] of Object.entries(terms)) {
  const hits = Object.entries(views).flatMap(([v, t]) => (t.match(re) ?? []).map((m) => `${v}: "${m}"`));
  console.log(`${k}: ${hits.length}${hits.length ? "  -> " + [...new Set(hits)].slice(0, 5).join(" | ") : ""}`);
}
console.log("\n=== FIRST VIEW TEXT ===\n" + views["first view"].replace(/\n+/g, " / ").slice(0, 900));
console.log("\n=== PROOF TAB ===\n" + views["tab Proof"].replace(/\n+/g, " / "));
await b.close();
