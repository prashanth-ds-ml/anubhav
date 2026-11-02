import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// Replay mode only (no keys). Starts the real API, which also serves the built React app from web/dist.
const HERE = dirname(fileURLToPath(import.meta.url));
const PY = process.env.ANUBHAV_PYTHON ?? resolve(HERE, "..", process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  workers: 1, // one server process, and each new visitor's first calls cost seconds: parallel tests only measure contention
  expect: { timeout: 30_000 }, // a new visitor's first dashboard calls take 1 to 2 s each on a cold server
  use: {
    baseURL: "http://localhost:7870",
    permissions: ["microphone"],
    // A fake microphone, so the recording flow can be tested without hardware
    launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] },
  },
  webServer: {
    command: `"${PY}" -m uvicorn anubhav.api.app:app --port 7870`,
    cwd: "..",
    // Keys blanked so a developer's .env can't turn live mode on: the suite must see what a keyless host shows
    env: { ANUBHAV_PUBLIC: "1", PYTHONIOENCODING: "utf-8", meta_api: "", baseten_api_key: "" },
    url: "http://localhost:7870/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
