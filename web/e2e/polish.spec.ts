import { test, expect } from "@playwright/test";

const TOOL = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?";

test("tabs follow the keyboard pattern: arrows, Home and End, one tab stop", async ({ page }) => {
  await page.goto("/");
  const orders = page.getByRole("tab", { name: "Orders" });
  await orders.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Route plans and drafts" })).toBeFocused();
  await expect(page.getByRole("tab", { name: "Route plans and drafts" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Ledger" })).toBeFocused();
  await page.keyboard.press("ArrowRight"); // wraps around
  await expect(orders).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Ledger" })).toHaveAttribute("aria-selected", "true");
  expect(await page.getByRole("tablist", { name: "Company data" }).locator('[role="tab"][tabindex="0"]').count()).toBe(1);
  expect(await page.getByRole("tablist", { name: "Main" }).locator('[role="tab"][tabindex="0"]').count()).toBe(1);
  await expect(page.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", /tab-/);
});

test("one theme: the page stays white even when the system asks for dark, and there is no theme switch", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Try it: seven scenarios" })).toBeVisible();
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(246, 248, 248)");
  await expect(page.getByRole("button", { name: /theme/i })).toHaveCount(0);
});

test("on a phone the explainer folds away and the chat input is near the top", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const about = page.locator("details.about");
  await expect(about).toBeVisible();
  expect(await about.evaluate((e: HTMLDetailsElement) => e.open)).toBe(false);
  await about.getByText("How it works").click();
  await expect(page.getByText("Drafts only")).toBeVisible();
  await about.getByText("How it works").click();
  await expect(page.getByText("Drafts only")).toBeHidden();
  await expect(page.getByLabel("Ask the agents")).toBeInViewport();
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over).toBeLessThanOrEqual(0);
});

test("on a phone, tables scroll inside their box, not the page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("tab", { name: "Fleet" }).click();
  await expect(page.getByRole("cell", { name: "V01" })).toBeVisible();
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over).toBeLessThanOrEqual(0);
});

test("the live region announces key moments only, not every card", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".timeline[aria-live]")).toHaveCount(0);
  // Record every value the status region takes, so a fast replay cannot hide an early announcement.
  await page.evaluate(() => {
    const seen: string[] = ((window as any).__announced = []);
    const el = document.querySelector(".chat > p.sr-only[role=status]")!;
    new MutationObserver(() => el.textContent && seen.push(el.textContent)).observe(el, { childList: true, characterData: true, subtree: true });
  });
  await page.getByRole("button", { name: TOOL }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible({ timeout: 20_000 });
  const seen: string[] = await page.evaluate(() => (window as any).__announced);
  expect(seen).toContain("Handing off to tool_forge");
  expect(seen.some((t) => t.startsWith("Answer ready"))).toBe(true);
  expect(seen.every((t) => /^(Handing off|Answer ready|Retry|Waiting)/.test(t))).toBe(true); // no tool calls or results
  expect(seen.length).toBeLessThanOrEqual(3);
});

test("the ledger reads like sentences, not JSON", async ({ page }) => {
  await page.goto("/#ledger");
  await expect(page.getByRole("row").nth(1)).toBeVisible();
  const text = await page.getByRole("tabpanel").innerText();
  expect(text).not.toMatch(/"stop"|cost_usd|agent_run_id/);
  await expect(page.getByLabel("Decision")).toContainText("Handed off work");
});

test("page has a favicon, a description and a descriptive title", async ({ page, request }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Anubhav.*truck loads/);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /never dispatches without a person/);
  const href = await page.locator('link[rel="icon"]').getAttribute("href");
  expect((await request.get(href!)).status()).toBe(200);
});

test("touch targets are at least 44px tall for the main controls", async ({ page }) => {
  await page.goto("/");
  for (const loc of [page.getByRole("tab", { name: "Orders" }), page.getByRole("button", { name: "Send" }), page.getByRole("button", { name: "Record a voice message" }), page.getByRole("button", { name: "About" })]) {
    const box = await loc.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(43.5);
  }
});

for (const width of [1024, 1440]) {
  test(`the Plan a truck button is fully on screen at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    const btn = page.getByRole("button", { name: /^Plan a truck for / }).first();
    await expect(btn).toBeVisible();
    const box = (await btn.boundingBox())!;
    const panel = (await page.locator("aside.right").boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(panel.x + panel.width - 8); // not clipped by the panel edge
    await expect(page.getByRole("row").first()).toContainText(/Order/);
  });
}

test("inside a cross-site frame (the Hugging Face Space page) the visitor is kept from one request to the next", async ({ page }) => {
  // Browsers drop the cookie in a cross-site iframe; the page sends the id the server gave it as a header instead.
  await page.route("**/api/**", async (r) => {
    const h = { ...r.request().headers() };
    delete h["cookie"];                                   // as a browser does in a cross-site frame
    if (!r.request().url().includes("/api/session")) return r.continue({ headers: h });
    try {                                                 // shown as live-capable, so S0 can start (nothing here calls a model)
      const res = await r.fetch({ headers: h });
      const s = await res.json();
      await r.fulfill({ response: res, json: { ...s, models: { ...s.models, "Muse Spark 1.3": { available: true, reason: null } }, live_runs_left: 8 } });
    } catch { /* the test ended while this was in flight */ }
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start S0" }).click();
  const guide = page.getByRole("region", { name: /Scenario S0/ });
  await guide.getByRole("button", { name: "Start fresh" }).click();
  await expect(guide.getByRole("status")).toContainText("Started fresh: 0 lessons");
  await page.getByRole("tab", { name: "Learning" }).click();
  const knows = page.getByRole("status", { name: "What this workspace knows" });
  await expect(knows).toContainText("0 lessons");          // a new visitor would have the 10 recorded lessons
  await expect(knows).toContainText("started fresh");
});
