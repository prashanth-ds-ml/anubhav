---
tags: [tracker, cost]
---
# Cost ledger: Meta API ($150) and Baseten ($100) credits

| Credit | Total $ | Spent $ | Left $ | Used for |
|---|---|---|---|---|
| Meta Model API | 150.00 | ~0.07 | ~149.93 | Muse Spark + Voice Transcribe runtime, evals |
| Baseten | 100.00 (+2M TPM) | 0.00 | 100.00 | Open-weights arm (FR-15) |

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
| | | | | | | | | |

### Prices
Model: always `meta-models/muse-spark-open-1026` (the hackathon override of `meta-models/muse-spark-open` in Baseten's docs), via the per-token Model API at `https://inference.baseten.co/v1`. Fill in per-token prices from Baseten.

## Partner credits
| Partner | Amount | Status | Use |
|---|---|---|---|
| Meta Model API | $150 | ✅ received | Core runtime |
| Baseten | $100 + 2M TPM | ✅ received (2026-10-27) | Open-weights arm (FR-15) |
| Modal | $100 | ⏳ pending | Open-weights arm / hosting alternative |
| Fireworks | $25 | ⏳ pending (applied 2026-10-27) | Selective; email only |
