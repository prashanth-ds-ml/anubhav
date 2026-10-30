---
tags: [tracker, errors]
---
# Errors and fixes

Every bug, failed call or surprise goes here, so we never debug the same thing twice. Template: `templates/error`.
Summary table first, details below. Newest at the bottom.

| ID | Date | Area | Symptom | Severity | Status | Fix commit |
|---|---|---|---|---|---|---|
| E-001 | 2026-10-27 | voice | Realtime ASR closed with "Ingress audio slower than real-time"; script hung until Ctrl-C | high | fixed | see below |
| E-002 | 2026-10-27 | voice | Live voice test saved 20 s of digital silence; empty transcript | high | fixed (use `--device 0`) | no code change |
| E-003 | 2026-10-27 | infra | Baseten returned 403 "please check the api-key you provided" | medium | fixed | no code change |
| E-004 | 2026-10-29 | infra | `scripts/data/build_db.py` was never committed; README told users to run it | medium | fixed | 331e6e9 |
| E-005 | 2026-10-29 | infra | `gh repo rename` returned HTTP 404 | low | fixed | no code change |
| E-006 | 2026-10-29 | data | Allocation mismatch: an order listed the same product twice | medium | fixed | generator commit |
| E-007 | 2026-10-29 | data | Overlap validator missed two trips starting at the same minute (caught by a mutation test) | medium | fixed | generator commit |
| E-008 | 2026-10-29 | data | Negative delivered quantity after a full weighbridge offload | medium | fixed | generator commit |
| E-009 | 2026-10-29 | data | Planned evidence lost: exposure orders hit random credit holds / rollovers | medium | fixed | generator commit |
| E-010 | 2026-10-29 | data | Unrealistic scale behaviour: 29% rollovers, 528 dairy spoilages, repeated expired-paper picks | high | fixed | generator commit |
| E-011 | 2026-10-29 | infra | Inline bash heredocs turned `\n` into real newlines inside Python source | low | fixed (use the Edit tool or script files) | — |
| E-012 | 2026-10-29 | data | Staff edits wrote the Jangaon limit into the T01 site master during history, so the 'unwritten' rule was written | high | fixed (D-033) | layer 2 commit |
| E-013 | 2026-10-29 | tools | find_site matched 'Pedda godown' to 'Bhavani Logistics Godown' on the generic word 'godown' | high | fixed (generic words ignored) | layer 2 commit |
| E-014 | 2026-10-29 | tools | A retry after cancel returned the cancelled draft (shared idempotency key), bypassing new policy checks | high | fixed (cancelled drafts never resurrected; test) | layer 2 commit |
| E-015 | 2026-10-29 | infra | Rename sweep skipped every folder named `data` (incl. src/anubhav/data, tests/data); tests caught the stale import | low | fixed | layer 2 commit |
| E-016 | 2026-10-29 | agent | Telugu-script request answered in Roman Telugu; reply offered to dispatch on confirmation (no such capability) | medium | fixed (system prompt: same script; 'you cannot dispatch') | layer 2 commit |
| E-017 | 2026-10-30 | tools | 'Plan tomorrow' (T03, 21 orders) hit the 12-call limit: tools only looked at one site/vehicle at a time, so no plan was made | high | fixed (D-037: plan_board, check_load, batch drafts; live check: 16 drafts in 11 calls) | tools commit |
| E-018 | 2026-10-30 | agent | A run that ended at the limit showed the previous turn's answer (reply taken from the whole conversation); no final answer was asked for | medium | fixed (reply from this turn only; wrap-up call with no tools at the limit; tests) | tools commit |
| E-019 | 2026-10-30 | infra | `requirements.txt` pinned `pywin32` with no platform marker, so a Linux / Streamlit Cloud install would fail | high | fixed (`uv pip compile --universal`) | step-1 commit |
| E-020 | 2026-10-30 | ui | Live buttons crashed with `KeyError: 'meta_api'` without keys, and some skipped the spend cap | high | fixed (one guard `core.live_client`; 60/day cap; AppTest) | step-1 commit |
| E-021 | 2026-10-30 | ui | Replay offered 23/48 request–company pairs with no saved run (a dead end); hosted visitors shared drafts and lessons | high | fixed (`core.replayable`; per-visitor state when `ANUBHAV_PUBLIC=1`) | step-1 commit |
| E-022 | 2026-10-30 | tools | An impossible date (`2026-02-30`) or any tool bug crashed the run; a reused idempotency key returned another draft; a duplicate order id counted its load twice | high | fixed (`BAD_ARGS`, catch-all `INTERNAL`, `CONFLICT`, dedupe; tests) | step-1 commit |
| E-023 | 2026-10-30 | learning | Revoking a pack retired the recipient's own lesson; pack ids collided within a second; pack text went into the prompt unfiltered | high | fixed (own lessons only lose the confirmation; date + uuid ids; per-kind allow-list, 40-char plain text; tests) | step-1 commit |
| E-024 | 2026-10-30 | agent | A failed model call (timeout, 5xx) crashed the run and lost its drafts; the client had no timeout or retries | medium | fixed (90 s timeout, 3 retries, `stop="error"` keeps drafts; offline httpx test) | step-1 commit |
| E-025 | 2026-10-30 | agent | World facts left in code (D-034): `"repu" = tomorrow` and "Telangana, 3PL" in the prompt; e-way-bill limit, max stops and 38 km/h in code; a `bandi/lorry/truck` list in the gate | medium | fixed (`configs/operating_rules.yaml`, speed from the world config, generic vehicle words learned per company) | step-1 commit |

**Areas:** model API · MCP · tools · agent · retrieval · verifier · voice · UI · infra · data · cost

## Patterns (update when 2+ errors share a cause)
- 

---

### E-001: Realtime ASR "Ingress audio slower than real-time"
- **Date:** 2026-10-27 · **Severity:** high · **Status:** fixed
- **Area:** voice (`scripts/smoke/live_voice.py`)
- **Symptom:** The server sent an `error` event, "Ingress audio slower than real-time", then closed. The send loop sat blocked on `queue.get()` until the user pressed Ctrl-C.
- **Repro:** Run `live_voice.py` from the VS Code terminal with the default mic (Intel mic array, MME).
- **Root cause:**
  1. The script opened the mic at 24 kHz, but the device runs natively at 44.1 kHz. Windows resampling delivered frames slower than real time.
  2. The sender was paced by mic callbacks, so any stall starved the server.
  3. A server error in the reader task never stopped the sender.
- **Fix:**
  - Capture at the device's native rate and resample to 24 kHz in numpy.
  - A clock-paced sender sends one 80 ms block per tick, padding with silence if the mic stalls.
  - The sender loop stops when the reader task ends, and server errors are re-raised as a clean message.
  - Added a mic level meter, `--list-devices`, and a warning when too many blocks are padded.
- **Prevention:** For realtime audio, always pace on the clock, not on input callbacks. Always capture at the device's native rate.
- **Time lost:** ~20 min

---

### E-002: Live voice recording is silent
- **Date:** 2026-10-27 · **Severity:** high · **Status:** fixed
- **Area:** voice (`scripts/smoke/live_voice.py`)
- **Symptom:** The user spoke for the whole run, but `voice/clean_20261027_021945.wav` is 20 s with peak amplitude 1 and 99.4% zero samples. The transcript came back empty. No "padded blocks" warning, so the mic did deliver frames; they were just zeros.
- **Finding:** A 1.5 s ambient check per input device showed that device 1 (Intel mic array, MME, the default) returns silence (peak 1). Device 0 (Microsoft Sound Mapper, MME) returns a real noise floor (rms ~129, peak ~1745).
- **Fix:** Re-ran with `--device 0` (Sound Mapper) at 09:04; the transcript was correct. Use `--device 0` on this laptop.
- **Prevention idea:** Warn when the recorded audio is near-silent (e.g. peak < 100), not just when blocks are padded.

---

### E-003: Baseten key rejected (403)
- **Date:** 2026-10-27 · **Severity:** medium · **Status:** fixed
- **Area:** infra (Baseten Model API)
- **Symptom:** Every call to `https://inference.baseten.co/v1` returned 403 "please check the api-key you provided", with both `Api-Key` and `Bearer` auth and with the correct model.
- **Root cause:** The key in `.env` was missing its last character (12.31 characters instead of 12.32).
- **Fix:** The owner re-pasted the full key into `.env` as `baseten_api_key`. Call verified with the OpenAI SDK and with LangChain `ChatOpenAI`.
- **Gotchas found:**
  - Only `meta-models/muse-spark-open-1026` works with the hackathon key; plain `meta-models/muse-spark-open` returns 403.
  - The model always reasons; the reasoning comes back in `message.reasoning_content`, separate from `content`.
  - Replies can contain emoji, so scripts must call `sys.stdout.reconfigure(encoding="utf-8")` on Windows or printing crashes.
- **Prevention:** After pasting a key, check it with a 1-call smoke test right away.

---

### E-004: build_db.py silently ignored by git
- **Date:** 2026-10-29 · **Severity:** medium · **Status:** fixed
- **Area:** infra (`.gitignore`)
- **Symptom:** A fresh clone had no `scripts/data/build_db.py`, although the README said to run it.
- **Root cause:** The `.gitignore` line `data/` matches *any* folder named `data`, including `scripts/data/`.
- **Fix:** Anchor the pattern: `/data/` (plus `archive/prototype_experiments/data/`).
- **Prevention:** Anchor ignore patterns with a leading `/` when they mean the repo root. Check `git status --ignored` before pushing.

### E-005: gh repo rename returns 404
- **Date:** 2026-10-29 · **Severity:** low · **Status:** fixed
- **Area:** infra (GitHub CLI)
- **Symptom:** `gh repo rename` failed with HTTP 404 on `prashanth-ds-ml/meta-hackathon-telugu-agent`.
- **Root cause:** The active `gh` account is `kprashanth-ai`, which has only pull access to the repo.
- **Fix:** Run admin commands with the owner's token, without switching accounts: `GH_TOKEN=$(gh auth token --user prashanth-ds-ml) gh ...`
- **Prevention:** Check `gh auth status` when a GitHub API call returns 404 on a repo you know exists.

### E-006 to E-010: found by the generator's tests and the realism loop (2026-10-29)
- **E-006 duplicate SKU lines:** test orders for planted evidence added extra lines of a product already on the order, so shipment allocation didn't reconcile. **Fix:** one line per product (as on a real order). **Prevention:** the integrity validator reconciles allocation per (order, SKU).
- **E-007 same-minute overlap:** the vehicle-overlap check used a strict `<`, so two trips starting at the same minute passed. A mutation test caught it. **Fix:** also flag equal start times. **Prevention:** every validator has a mutation test.
- **E-008 negative quantity:** after a weighbridge offload took all cases of a product, "partial acceptance" still subtracted one. **Fix:** only when cases remain.
- **E-009 lost evidence:** a planned Jangaon exposure order was randomly put on credit hold, so the rule left no trace in the pilot. **Fix:** planned-evidence orders skip random cancellations/holds; false notes fire on the first delivery on/after their date. **Prevention:** a test asserts every planned exposure happens.
- **E-010 scale realism:** the full run passed every check but wasn't realistic. Fixes:
  - load splitting across two trucks;
  - vehicles blocked until their papers are renewed;
  - one client brand per order;
  - chilled loads wait for a reefer (the ice-box shortcut is occasional, and spoils only half the time);
  - the bridge closure only affects legs that cross it.

  **Prevention:** rate tests on the full world (rollovers < 6%, returns < 3%, Roman Telugu > Telugu > English).
- **Lesson:** "0 critical problems" is necessary, not sufficient. Always read samples and look at rates at full scale.
