---
tags: [tracker, smoke]
---
# Day-1 Muse smoke tests

The gate for Day 1: **T2 passes, and the T6 voice decision is made.** Scripts are in `scripts/smoke/`, raw JSON in `artifacts/smoke/`.
**Status (2026-10-27):** text gate ✅ PASSED · voice ⏳ waiting on recordings

## Model facts (from the Meta docs, checked 2026-10-27)
| Fact | Value | Source |
|---|---|---|
| API base URL | `https://api.meta.ai/v1` (OpenAI-compatible Chat Completions, Responses, Anthropic-compatible Messages) | dev.meta.ai/docs |
| Auth | `Authorization: Bearer <key>`; our env var is `meta_api` | docs |
| Muse Spark model ID | `muse-spark-1.3` (recommended); also 1.2 and 1.1 | /docs/models |
| Contributor variant | `muse-spark-1.3-contributor` (≈12× cheaper; prompts may be used for training; 150 RPM) | /docs/pricing-rate-limits |
| Muse Voice Transcribe ID | `muse-voice-transcribe-1.0`, `POST /v1/asr/transcribe` (multipart: `request` JSON + `audio` WAV) | /docs/speech-to-text |
| Transcribe languages | 25 languages **including Telugu**, with code-switching. `languageBias` takes names (`["Telugu","English"]`); `keywords` biases spellings | /docs/speech-to-text |
| Transcribe audio limits | Mono 16-bit PCM WAV at 16 or 24 kHz; ≤32 MB; ≤10 min | same |
| Price: Spark 1.3 | $1.25 / 1M input · $4.25 / 1M output · $0.15 / 1M cached input | pricing page |
| Price: Spark 1.3 contributor | $0.10 / 1M input · $0.20 / 1M output | pricing page |
| Price: Transcribe | $0.18 per audio hour | speech docs |
| Rate limits | Spark 1.3: 3,000 RPM / 4M TPM per team | pricing page |
| Context window | 1,048,576 tokens | /docs/models |
| tool_choice | **Only `"auto"`** (`"none"`, `"required"` and named choices return 400) | /docs/tool-calling |
| Parallel tool calls | On by default (`parallel_tool_calls`) | same |
| Max tools | Not stated; for large sets, docs suggest `defer_loading` + `tool_search` | same |
| `strict` schemas | Validates the schema only; **arguments are not guaranteed**, so validate them in code | same |
| Temperature / seed | Accepted, but **not deterministic** (see T8) | our test |
| Audio into Spark | 1.3: "audio understanding isn't fully supported"; docs recommend 1.2 for audio | /docs/models |

## Results (model `muse-spark-1.3`, 2026-10-27)
| # | Test | Pass criterion | Result | Notes |
|---|---|---|---|---|
| T1 | Basic chat call | Response received | ✅ | 4.2 s; 14 in / 163 out tokens. Hidden reasoning tokens are billed as output |
| T2 | Tool call from Roman Telugu (3 tools) | Valid call, correct args | ✅ | **Parallel** `find_customer("Ravi Traders")` + `check_stock("Sunrise sunflower oil 1L")`, 4.9 s |
| T3 | Same in Telugu script | Valid call | ✅ | Same tools; Telugu converted to Roman script in the args ("Ravi Traders"), 4.2 s |
| T4 | Negation, first turn ×3 | No confirm | ✅ 3/3 | |
| T4b | Negation, **full loop** with fake tools ×3 | No `confirm_order`; draft created | ✅ 3/3 | Every run: find_customer → check_stock → create_draft_quote. It noted the 4-carton shortfall and said "Order confirm cheyyaledu" ("didn't confirm the order") in Telugu |
| T5 | 40 tool schemas | Accepted; correct tools picked | ✅ | 40 accepted; still picked the right 2. ~3k input tokens (vs ~0.8k with 3 tools), 7.0 s. **Arm A is feasible** |
| T6 | Self-recorded voice notes | Transcripts can drive T2 | ✅ (1 of 3 notes) | Live mic run 2026-10-27 09:04 on `--device 0`: accurate Telugu script, English words kept in English. Still to do: noisy note and an order-style note with `--agent` |
| T7 | Pricing known | Yes | ✅ | See the facts table |
| T8 | Temperature 0 + seed ×3 | Identical outputs | ❌ (expected) | 2 of 3 identical. **Not deterministic**, so we keep the ×3 repeats (D-008) |

**Smoke-test spend:** ≈ $0.07 (≈17k input / 9k output tokens).

## Observations that affect the design
1. **Muse calls tools in parallel by default.** The LangGraph agent must handle several tool calls per turn.
2. **No `tool_choice: none/required`.** We can't force a final answer through the API, so the graph's own turn limit has to stop the loop.
3. **Tool arguments aren't schema-guaranteed.** Validate them in the MCP tool layer (this was already planned).
4. **Discounts weren't checked in T4b** because no discount tool was offered. This is a reminder that retrieval has to surface `get_discount_eligibility` for "discount eligible aithe apply cheyyi" ("apply the discount if eligible"). It's a good candidate failure for the improvement-loop demo.
5. **Replies come back in the user's language/script mix** (Telugu script or Roman Telugu). Good for the demo.
6. 40 tools work directly. BigTool's value is therefore **token cost and latency**, ~3.7× fewer input tokens per turn, which confirms D-007.

## Voice transcripts (T6): to fill in
Record 3 notes (phone voice memo is fine; any format; ffmpeg converts), save them in `voice/` (gitignored), then run:
`uv run python scripts/smoke/smoke_voice.py voice/* --keywords "Ravi Traders,Sunrise,sunflower oil,cartons"`

| Note | What I said | What Muse transcribed (plain / biased) | Usable? |
|---|---|---|---|
| 1 clean Telugu | | | |
| 2 code-mixed (live mic, `clean_20261027_090415.wav`) | Self-intro in Telugu with English words | నా పేరు ప్రశాంత్ మరి నీ పేరు ఏంటి నేను Muse AI Global Developer Hackathon కి పని చేస్తున్నాను. So, నీ help నాకు కావాలి. | ✅ owner: "kinda good and working" |
| 3 noisy | | | |

## Decision
- Voice: ✅ go. Live Telugu / code-mixed transcription works (owner-confirmed 2026-10-27). Voice stays P0 (D-003)
- Arm A: ✅ feasible (40 schemas accepted)
