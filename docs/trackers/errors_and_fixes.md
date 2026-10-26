---
tags: [tracker, errors]
---
# Errors and fixes

Every bug, failed call or surprise goes here, so we never debug the same thing twice. Template: `templates/error`.
Summary table first, details below. Newest at the bottom.

| ID | Date | Area | Symptom | Severity | Status | Fix commit |
|---|---|---|---|---|---|---|
| E-001 | 2026-10-27 | voice | Realtime ASR closed with "Ingress audio slower than real-time"; script hung until Ctrl-C | high | fixed | see below |

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
