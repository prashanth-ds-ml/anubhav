import { chromium } from "@playwright/test";
const OUT = process.argv[2];
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await p.goto("http://localhost:7860/");
await p.getByRole("row").nth(1).waitFor({ timeout: 30000 });
await p.getByRole("button", { name: /Hanamkonda lo ae weekday/ }).click();
await p.waitForTimeout(2600);
await p.screenshot({ path: `${OUT}/r1_midrun.png` });
await p.locator(".bubble.answer").waitFor({ timeout: 30000 });
for (const t of ["Route plans and drafts", "Learning", "Proof", "Agents"]) {
  await p.getByRole("tab", { name: t }).click();
  if (t.startsWith("Route")) await p.getByText("Why this plan").first().click();
  await p.waitForTimeout(400);
  await p.screenshot({ path: `${OUT}/r2_${t.split(" ")[0]}.png` });
}
await b.close();
