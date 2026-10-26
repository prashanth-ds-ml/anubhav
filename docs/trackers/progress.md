---
tags: [tracker, progress]
---
# Progress tracker

**Overall:** 5% (planning done; build not started)
Status key: ⬜ pending · 🟨 in progress · ✅ done · ❌ blocked

| Day | Date (IST) | Focus | Gate | Status | Evidence |
|---|---|---|---|---|---|
| 0 | Oct 26–27 | Docs review, PRD v1.1, day plan, Obsidian vault | Plan agreed | ✅ | [[PRD_v1.1]], [[day_plan]] |
| 1 | Tue Oct 27 | Muse smoke tests, repo, SQLite seed, mock adapter | Roman-Telugu tool call works; voice decision made | 🟨 text gate ✅, voice ⏳ | [[smoke_tests]] |
| 2 | Wed Oct 28 | MCP server + 12 core tools + contract tests | Golden quote correct without the LLM | ⬜ | |
| 3 | Thu Oct 29 | LangGraph agent, trace, verifier, safety guard | **HARD CHECKPOINT:** golden path runs live | ⬜ | |
| 4 | Fri Oct 30 | 40 tools, BigTool, voice path, first X post | Arms A and B run on the same scenario | ⬜ | |
| 5 | Sat Oct 31 | 48-task benchmark, baseline, failure catalog | Baseline logged | ⬜ | |
| 6 | Sun Nov 1 | Improvement loop | One real candidate probed and decided | ⬜ | |
| 7 | Mon Nov 2 | UI, held-out ×3, hosted demo, README, **freeze** | Fresh install and hosted link both work | ⬜ | |
| 8 | Tue Nov 3 | Video and submission dry run | Video ≤ 3:00; links work in incognito | ⬜ | |
| 9 | Wed Nov 4 | Buffer, then **submit** | Submitted | ⬜ | |

## Feature status (PRD §6)
| FR | Feature | Priority | Status |
|---|---|---|---|
| FR-01 | 4 input language styles | P0 | ⬜ |
| FR-02 | LangGraph agent, bounded | P0 | ⬜ |
| FR-03 | MCP server + SQLite simulator | P0 | ⬜ |
| FR-04 | Draft quote with approval boundary | P0 | ⬜ |
| FR-05 | Trace and replay | P0 | ⬜ |
| FR-06 | Deterministic verifier | P0 | ⬜ |
| FR-07 | Human-approved improvement workflow | P0 | ⬜ |
| FR-08 | BigTool switch | P0 | ⬜ |
| FR-09 | 40 tools, all tested | P0 (fallback 25) | ⬜ |
| FR-10 | 3-view UI | P0 | ⬜ |
| FR-11 | Voice input | P0 (gated) | ⬜ |
| FR-12 | Muse diagnostician/proposer | P0 | ⬜ |
| FR-13 | Paraphrase self-verification | P1 | ⬜ |
| FR-14 | Hosted demo | P0 | ⬜ |
| FR-15 | Open-weights arm | P1 (conditional) | ⬜ |
| FR-16 | Manual-vs-agent timing study | P0 | ⬜ |

## Acceptance tests (PRD §16)
| AT | Description | Status | Run id |
|---|---|---|---|
| AT-01 | Roman Telugu + English → correct draft | ⬜ | |
| AT-02 | Telugu script → ≥2 tools | ⬜ | |
| AT-03 | Ambiguous product → clarification | ⬜ | |
| AT-04 | "cheyyaku" → no committed order | ⬜ | |
| AT-05 | Retrieval miss logged | ⬜ | |
| AT-06 | Correction is a versioned diff; no self-promotion | ⬜ | |
| AT-07 | Sandbox probe on identical snapshots | ⬜ | |
| AT-08 | Regression rejects; rollback works | ⬜ | |
| AT-09 | Same frozen model before and after | ⬜ | |
| AT-10 | Fresh install, no secrets, replay works | ⬜ | |
| AT-11 | Voice drives golden path | ⬜ | |
| AT-12 | Paraphrase probes never leak into held-out | ⬜ | |
| AT-13 | Hosted demo works in incognito; spend cap enforced | ⬜ | |
