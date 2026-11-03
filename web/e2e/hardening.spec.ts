import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Sprint 7: every main tab passes the accessibility check (with the system set to light, and to dark: the page stays white), and no page scrolls sideways on a laptop or
// a phone (a wide chart scrolls inside its own box instead).

const TABS: [string, string][] = [
  ["/", "Try it: seven scenarios"],
  ["/#plans", "Try it: seven scenarios"],
  ["/#learning/L-T01-002", "What it has learned"],
  ["/#learning/L-T01-011", "What it has learned"],
  ["/#tools", "Repeated questions that could become tools"],
  ["/#agents", "Each agent has its own way to learn"],
  ["/#runs", "Runs you can inspect"],
  ["/#proof/bench", "Every experiment we pre-registered, including the ones that failed"],
  ["/#proof/claims", "Not measured yet"],
];

async function open(page: Page, url: string, heading: string) {
  await page.goto(url);
  await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  await page.waitForTimeout(400); // charts and lists that load after the heading
}

for (const scheme of ["light", "dark"] as const) {
  test(`every main tab passes the accessibility check in ${scheme} mode`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const found: string[] = [];
    for (const [url, heading] of TABS) {
      await open(page, url, heading);
      const axe = await new AxeBuilder({ page }).analyze();
      found.push(...axe.violations.map((v) => `${url} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`));
    }
    expect(found).toEqual([]);
  });
}

for (const [w, h] of [[1024, 768], [390, 844]]) {
  test(`no page scrolls sideways at ${w} wide`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    const wide: string[] = [];
    for (const [url, heading] of TABS) {
      // On a phone the main tabs are a select; the headings are the same.
      await open(page, url, heading);
      const m = await page.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }));
      if (m.s > m.c + 1) wide.push(`${url}: ${m.s} > ${m.c}`);
    }
    expect(wide).toEqual([]);
  });
}
