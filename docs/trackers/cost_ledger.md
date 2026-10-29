---
tags: [tracker, cost]
---
# Cost ledger: Meta API ($150) and Baseten ($100) credits

| Credit | Total $ | Spent $ | Left $ | Used for |
|---|---|---|---|---|
| Meta Model API | 150.00 | ~14.42 | ~135.58 | Muse Spark + Voice Transcribe runtime, evals |
| Baseten | 100.00 (+2M TPM) | ~15.6 | ~84.4 | Open-weights arm (FR-15) |

## Meta Model API ($150)

**Spend-limit notification set on Billing:** ⬜
**Stop-and-replan rule:** if any day spends more than ~$22 (15%), pause and review.

### Budget (from PRD §12; fill in once pricing is known)
| Bucket | Target % | Target $ | Spent $ | Left $ |
|---|---|---|---|---|
| Dev / debugging | ≤25% | 37.50 | | |
| Benchmark runs | ≤40% | 60.00 | | |
| Improvement loop | ≤15% | 22.50 | | |
| Hosted live mode | ≤10% | 15.00 | | |
| Reserve | ≥10% | 15.00 | | |
| **Total** | 100% | **150.00** | | |

### Daily spend
| Date | Bucket | Runs | Tokens in | Tokens out | Audio min | $ | Cumulative $ | Billing page check |
|---|---|---|---|---|---|---|---|---|
| 2026-10-27 | Dev | 14 calls (smoke) | ~17k | ~9k | 0.03 (tone test) | ~0.07 | ~0.07 | ⬜ |
| 2026-10-27 | Dev | 2 live voice tests (1 silent mic, 1 good) | | | 0.67 | 0.002 | ~0.07 | ⬜ |
| 2026-10-27 | Benchmark | Sample baseline: 5 tasks, 36 tool calls (`sample_run.py`) | | | | 0.131 | ~0.20 | ⬜ |
| 2026-10-27 | Benchmark | EXP-001 run 1 (core, 96 runs) + runner tests | | | | 2.41 | ~2.61 | ⬜ |
| 2026-10-27 | Benchmark | Arm B smoke tests (incl. one 36-call loop from our namespace bug) | | | | 0.37 | ~2.98 | ⬜ |
| 2026-10-27 | Benchmark | EXP-001 run 2 (core) + EXP-002 arms A and B (288 runs) + 4 re-runs | | | | 10.59 | ~13.57 | ⬜ |
| 2026-10-27 | Benchmark | EXP-003 Lab head-to-head (5 scenarios × 3 repeats, ~60 calls) | | | | 0.85 | ~14.42 | ⬜ |
| 2026-10-27 | Research | Interview audio transcription (13 min, 7 chunks; transcript kept off-repo) | | | 13.3 | ~0.04 (est.) | ~14.46 | ⬜ |
| 2026-10-27 | Benchmark | EXP-005 dispatch probe, Spark 1.3 (16 tasks × 2) | | | | 0.71 | ~15.17 | ⬜ |
| 2026-10-27 | Benchmark | EXP-006 history mining, Spark 1.3 (2 runs) | | | | 0.09 | ~15.26 | ⬜ |
| 2026-10-29 | Voice | Muse Voice Transcribe pipeline check (20 s, Day-1 recording) | | | | 0.001 | ~15.26 | ⬜ |

### Prices (verified 2026-10-27)
| Model | Input /1M | Output /1M | Cached /1M |
|---|---|---|---|
| muse-spark-1.3 | $1.25 | $4.25 | $0.15 |
| muse-spark-1.3-contributor | $0.10 | $0.20 | $0.002 |
| muse-voice-transcribe-1.0 | $0.18 per audio hour | | |

**Rough per-task estimate (1.3 standard):** ~5 turns × ~3k in / ~0.6k out ≈ $0.03 per task. 48 tasks × 3 arms ≈ $4.50. 16 held-out × 3 repeats × 2 arms ≈ $3. **The $150 is ample on the standard model.**

## Baseten ($100 + 2M TPM)

**Spend alert set on Baseten billing:** ⬜

### Daily spend
| Date | Model / deployment | Runs | Tokens in | Tokens out | GPU min | $ | Cumulative $ | Billing page check |
|---|---|---|---|---|---|---|---|---|
| 2026-10-27 | muse-spark-open-1026 (Model API) | 3 key-check calls ("Hello!") | ~147 each (128 cached) | ~27 each | | <0.01 | <0.01 | ⬜ |
| 2026-10-27 | muse-spark-open-1026 (Model API) | EXP-004: probe + 2-task test + core and A arms (192 runs) | ~3.5M | | | ~5.9 (at tracker prices) | ~5.9 | ⬜ |
| 2026-10-27 | muse-spark-open-1026 (Model API) | EXP-005 dispatch probe: 1 smoke + 16 tasks × 2 | | | | 0.76 | ~6.7 | ⬜ |
| 2026-10-27 | muse-spark-open-1026 (Model API) | EXP-006 four arms (116 runs) | | | | 2.72 | ~9.4 | ⬜ |
| 2026-10-29 | muse-spark-open-1026 (Model API) | EXP-007 six arms (180 runs; raw-history arms have ~15k-char prompts) | | | | 5.93 | ~15.3 | ⬜ |
| 2026-10-29 | muse-spark-open-1026 (Model API) | Layer 2 live golden path: 5 requests (RT/TE/EN/MIX/ambiguous) + TE/RT rerun after prompt fix | | | | 0.29 | ~15.6 | ⬜ |

### Prices
Model: always `meta-models/muse-spark-open-1026` (the hackathon override of `meta-models/muse-spark-open` in Baseten's docs), via the per-token Model API at `https://inference.baseten.co/v1`. Fill in per-token prices from Baseten.

## Partner credits
| Partner | Amount | Status | Use |
|---|---|---|---|
| Meta Model API | $150 | ✅ received | Core runtime |
| Baseten | $100 + 2M TPM | ✅ received (2026-10-27) | Open-weights arm (FR-15) |
| Modal | $100 | ⏳ pending | Open-weights arm / hosting alternative |
| Fireworks | $25 | ⏳ pending (applied 2026-10-27) | Selective; email only |
