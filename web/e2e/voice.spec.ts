import { test, expect, type Page } from "@playwright/test";

const PLAN = "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.";
const on = { available: true, reason: null };
const off = { available: false, reason: "Voice is off here (no `meta_api` set)." };

// A session refresh can still be in flight when a test ends; drop it quietly.
test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

/** Ask the real server for the session, then say what voice looks like. */
async function caps(page: Page, voice: object) {
  await page.route("**/api/session", async (r) => {
    const res = await r.fetch();
    await r.fulfill({ response: res, json: { ...(await res.json()), voice } });
  });
}

async function record(page: Page) {
  await page.getByRole("button", { name: "Record a voice message" }).click();
  await expect(page.getByRole("button", { name: "Stop recording" })).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Stop recording" }).click();
}

test("voice is off with a visible reason when the backend says so; typing still works", async ({ page }) => {
  await caps(page, off);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Record a voice message" })).toBeDisabled();
  await expect(page.getByText("Voice works in live mode, which is off on this demo.")).toBeVisible();
  await page.getByLabel("Ask the agents").fill(PLAN);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".bubble.answer")).toBeVisible();
});

test("without keys the real server reports voice off (no mock)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Record a voice message" })).toBeDisabled();
  // The server says why in operator terms (no `meta_api` set); the page says it in plain words.
  await expect(page.getByText("Voice works in live mode, which is off on this demo.")).toBeVisible();
});

test("record, stop, transcript lands in the box for editing; nothing is sent until Send", async ({ page }) => {
  await caps(page, on);
  let sent: { type: string | undefined; riff: boolean } | null = null;
  await page.route("**/api/voice", async (r) => {
    const buf = r.request().postDataBuffer();
    sent = { type: r.request().headers()["content-type"], riff: buf?.subarray(0, 4).toString() === "RIFF" };
    await r.fulfill({ json: { transcript: PLAN, audio_ms: 3200, cost_usd: 0.0004 } });
  });
  await page.goto("/");
  await expect(page.getByText(/Audio goes to Meta's transcription service/)).toBeVisible();
  await record(page);
  const box = page.getByLabel("Ask the agents");
  await expect(box).toHaveValue(PLAN);
  await expect(page.getByText(/Heard 3\.2 s of audio/)).toBeVisible();
  expect(sent).toEqual({ type: "audio/wav", riff: true }); // a real 16 kHz WAV was posted
  await expect(page.locator(".bubble.user")).toHaveCount(0); // not sent yet
  await box.press("Enter");
  await expect(page.locator(".bubble.user")).toHaveText(PLAN);
  await expect(page.locator(".bubble.answer")).toBeVisible({ timeout: 20_000 });
});

test("a refusal from the server is shown in plain words, with no retry", async ({ page }) => {
  await caps(page, on);
  await page.route("**/api/voice", (r) => r.fulfill({ status: 403, json: { error: { code: "LIVE_OFF", message: "This session used its 8 live runs." } } }));
  await page.goto("/");
  await record(page);
  await expect(page.getByText("This session used its 8 live runs.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Try again/ })).toHaveCount(0);
});

test("a service failure keeps the recording and Try again resends it", async ({ page }) => {
  await caps(page, on);
  let calls = 0;
  await page.route("**/api/voice", (r) => {
    calls++;
    return calls === 1
      ? r.fulfill({ status: 502, json: { error: { code: "TRANSCRIBE_FAILED", message: "Transcription failed (TimeoutError). Try again." } } })
      : r.fulfill({ json: { transcript: "second try works", audio_ms: 1000, cost_usd: 0.0001 } });
  });
  await page.goto("/");
  await record(page);
  await expect(page.getByText(/Transcription failed/)).toBeVisible();
  await page.getByRole("button", { name: /Try again/ }).click();
  await expect(page.getByLabel("Ask the agents")).toHaveValue("second try works");
  expect(calls).toBe(2);
});

test("a silent recording asks the person to try again", async ({ page }) => {
  await caps(page, on);
  await page.route("**/api/voice", (r) => r.fulfill({ status: 422, json: { error: { code: "NO_SPEECH", message: "We could not hear any speech. Try again, closer to the microphone." } } }));
  await page.goto("/");
  await record(page);
  await expect(page.getByText(/could not hear any speech/)).toBeVisible();
  await expect(page.getByLabel("Ask the agents")).toHaveValue("");
});

test("blocked microphone permission explains how to fix it and keeps typing available", async ({ page }) => {
  await caps(page, on);
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError"));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Record a voice message" }).click();
  await expect(page.getByText(/Microphone access was blocked/)).toBeVisible();
  await expect(page.getByLabel("Ask the agents")).toBeEnabled();
});

test("transcript is appended to what was already typed", async ({ page }) => {
  await caps(page, on);
  await page.route("**/api/voice", (r) => r.fulfill({ json: { transcript: "and Hanamkonda too", audio_ms: 1000, cost_usd: 0.0001 } }));
  await page.goto("/");
  await page.getByLabel("Ask the agents").fill("Plan a truck");
  await record(page);
  await expect(page.getByLabel("Ask the agents")).toHaveValue("Plan a truck and Hanamkonda too");
});
