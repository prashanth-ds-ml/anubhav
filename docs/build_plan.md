---
tags: [plan, build]
date: 2026-10-29
---
# Build plan: Anubhavam (Oct 29 → Nov 4)

Source of truth for *what* to build: [[PRD_v3.1]] and [[Data_Benchmark_Blueprint_v1.0]], scaled by D-027 (**3 history companies + 1 new test company**; everything else kept).
This file says *in what order* and *when it is done*. Track daily status in [[progress]].

**Deadline:** Wed Nov 4, 9:00 PM ET = **Thu Nov 5, 7:30 AM IST**. Target: submit on Nov 4 IST.

## Ground rules
1. **Build in layers.** Each layer ends with something that works end to end. If time runs out, we stop at the last finished layer and still have a demo.
2. **Demo-safe checkpoint: Sat Nov 1, 10:00 AM IST.** Layers 0–3 must be done. If not, cut from the order in §5 and do not start Layer 4.
3. **Every module ships with tests.** Use mock mode (no credits) for development; spend credits only on pre-registered runs.
4. **Pre-register before spending:** hypothesis, frozen files and hashes, decision rule. Log in [[experiments]] and [[cost_ledger]].
5. **The model proposes, code enforces, people approve.** No safety check is ever done by the LLM.
6. **End every session** with: daily note, [[progress]], [[errors_and_fixes]], [[cost_ledger]], commit and push (no Claude trailer).

## The companies (fictional)
| ID | Company | Base | Role in the story | Schema variant |
|---|---|---|---|---|
| T01 | Warangal A (3PL) | Warangal | Site/entrance constraints, aliases; the Jangaon story | Adapter A: `fleet_vehicles`, `shipments`, `trip_notes` |
| T02 | Warangal B (3PL) | Warangal | Different carriers, same corridors; overlapping regional knowledge | Adapter B: `truck_master`, `loads`, `delivery_events` |
| T03 | Hyderabad (3PL) | Hyderabad | High-volume, multi-customer FMCG; different region (negative transfer control) | Adapter C: legacy consignment IDs, weight-unit variation |
| T-new | New test company | Seeded | Cold start: generated fresh from a seed; receives only the approved domain pack | Any of A/B/C, picked by seed |

## Target layout
```
src/anubhavam/
  muse.py              # Muse client (Spark, Spark Open, Voice Transcribe), cost + trace hooks
  data/                # world generator (blueprint scripts 01–08 as modules), validators
  mcp/                 # FastMCP server, tool manifests, tenant broker, adapters A/B/C
  agent/               # LangGraph graph: intake → … → record; specialists: planning, operations, experience
  safety/              # deterministic validator, units, atomic holds, roles, injection guards
  learning/            # Loop B: miner, evidence gate, lesson store, review, expiry, domain pack
  harness/             # Loop A: patch proposal, paired probes, versions, rollback
  eval/                # casebook builder, arms A–E runner, scorer, adversarial suite
  ui/                  # Streamlit: Workbench, Learning Lab, Benchmarks & Audit
tests/                 # mirrors src/anubhavam
data/ (git-ignored)    # generated SQLite: tenant_*.sqlite, learning.sqlite, evaluation.sqlite
benchmarks/            # dev/, sealed/, results/  (oracle_private/ is never committed)
```

---

## Layer 0: Truth check and setup · Thu Oct 29
| # | Task | Done when |
|---|---|---|
| 0.1 | **EXP-007 (Arm B check):** on the EXP-006 data, compare cold vs **raw-note retrieval** vs learned lessons | Pre-registered, run, result logged. If raw retrieval ≈ lessons, reframe the claim before building |
| 0.2 | Verify the external citations in PRD v3.1 (Harness² repo and arXiv, MCP spec link, LangGraph interrupts) | Each one opened and confirmed, or removed from the docs |
| 0.3 | Project setup: add dependencies (langgraph, mcp, pydantic, streamlit, ortools, faker), `src/anubhavam/` skeleton, Muse client ported with mock mode | `uv sync` and `pytest` pass on a clean clone |

## Layer 1: Data world · Thu Oct 29 → Fri Oct 30
| # | Task | Done when |
|---|---|---|
| 1.1 | World generator: geography, sites/entrances, products, carriers, vehicles, drivers, **hidden true rules with validity periods** | Seeded, hashed, and the hidden rules file stays separate from agent-visible data |
| 1.2 | Demand → shipments: customers, orders, order items (units, weights), allocation, consolidation and splits | Quantities reconcile; no unit mixing |
| 1.3 | Dispatch and outcomes simulation: trips, events, failures and returns caused by the hidden rules, delays, POD | Outcomes follow from rules plus noise, not hand-placed |
| 1.4 | Multilingual notes: driver/planner notes in EN/TE/RT/MIX, aliases, **misleading habits, stale rules, contradictions** | No note spells out a test answer |
| 1.5 | Validators (blueprint §7): structural, temporal, physical, operational, privacy, reproducibility | **Pilot first** (7 days, 1 company, ~100 orders), then full: 90 days × 3 companies + T-new; 0 violations |
| 1.6 | **You review** the pilot for realism (~1 h): 20 trips, 30 orders, the rules | Notes logged in [[data_and_benchmark]] |

## Layer 2: Agent runtime · Fri Oct 30 → Sat Oct 31
| # | Task | Done when |
|---|---|---|
| 2.1 | MCP server (FastMCP) with the PRD §6.3 tools, typed manifests (§6.4), adapters A/B/C to one contract | Contract tests pass for all 3 adapters with the same tests |
| 2.2 | Tenant broker: tenant/role from the session, never from the prompt; tool discovery by permission | Cross-tenant and role-spoof tests denied and audited |
| 2.3 | LangGraph graph: INTAKE → INTERPRET → CLARIFY? → DISCOVER → READ → PLAN → VALIDATE → DRAFT → EXPLAIN → RECORD, with turn/tool/cost limits | Golden path runs live in EN, TE, RT and MIX |
| 2.4 | Safety: units, capacity, dimensions, site rules, **atomic exclusive holds + idempotency**, draft-only boundary, typed errors | Overload, wrong-unit, double-booking (concurrent) tests pass |
| 2.5 | Trace store (JSONL + SQLite): inputs, tools, args, results, versions, cost, verdict; replay | Any run can be replayed and costed |
| 2.6 | Voice: Muse Voice Transcribe → transcript confirm → same path | One Telugu voice request produces a valid draft |

## Layer 3: Learning Loop B and sharing · Sat Oct 31
| # | Task | Done when |
|---|---|---|
| 3.1 | Miner: Muse reads history and proposes scoped candidate lessons with evidence and alternatives | Candidates saved with provenance |
| 3.2 | Evidence gate (code) and lesson state machine (OBSERVED → … → ACTIVE_ADVISORY/POLICY → CHALLENGED → RETIRED) | Habit rejected; one failure gives an advisory, not a ban |
| 3.3 | Review actions: approve, narrow, reject, require evidence, retire, roll back; audit trail | Each action tested |
| 3.4 | Use: approved lessons in the agent's context; enforced policies in the validator; contradictions challenge | New task gets the safer draft |
| 3.5 | Domain pack: rule-based private/regional filter, publish with approval, recipient opt-in, revocation | T-new is helped; 0 leaks; site-specific rules don't transfer to other sites |
| 3.6 | Weekly "What I learned" report | Generated from the lesson store |

### ✅ Demo-safe checkpoint: Sat Nov 1, 10:00 AM IST
The Jangaon story works end to end: wrong draft → mined lesson → review → right draft → T-new right on day 1, with a habit rejected and double-booking blocked.

## Layer 4: Loop A and planning depth · Sun Nov 1
| # | Task | Done when |
|---|---|---|
| 4.1 | Harness patch loop: detect → classify → propose bounded patch (allowed surfaces only) → paired probes → gate → approve → version/rollback | One real patch with matched baseline/candidate results and a decision |
| 4.2 | OR-Tools planning for consolidation and vehicle choice (small cases vs exact optimum) | Plans feasible; cost gap reported |
| 4.3 | Specialists (planning, operations, experience) vs one-generalist baseline | Compared before claiming any benefit |

## Layer 5: Benchmark · Sun Nov 1 → Mon Nov 2
| # | Task | Done when |
|---|---|---|
| 5.1 | Casebook builder: 100 sealed cases (Pack 1: 50, Pack 2: 50), dev/probe pool, private oracle | Leakage scan clean; split by scenario family and time |
| 5.2 | **You review** (3 passes, blueprint §9); log in [[data_and_benchmark]] | Reviewed count known; publish that denominator honestly |
| 5.3 | Adversarial suite: injection, tenant isolation, role spoof, concurrency, rollback, stale approval | All release gates at zero |
| 5.4 | Pre-register and run arms **A / B / C / D** (+ **E** transfer on T-new) | Paired results with counts, costs, failures |

## Layer 6: Product surface · Mon Nov 2
| # | Task | Done when |
|---|---|---|
| 6.1 | Streamlit: Workbench, Learning Lab, Benchmarks & Audit (PRD §13) | Full demo flow clickable |
| 6.2 | Live judge challenge: seed, company count, order count, difficulty → new world → run → replay | Same seed gives the same world; different seed works |
| 6.3 | Hosting with spend cap, rate limit, replay mode labelled | Works in incognito |

## Layer 7: Ship · Tue Nov 3 → Wed Nov 4
| # | Task | Done when |
|---|---|---|
| 7.1 | README, architecture diagram, attribution, limitations, results | Clean-clone install works |
| 7.2 | 3-minute video (PRD §16) | ≤ 3:00, subtitles, replay labelled |
| 7.3 | Submission dry run Nov 3; submit Nov 4 | Submitted before 9 PM ET |

---

## 5. Cut order (if behind)
Cut first → last: live judge challenge → specialists comparison → OR-Tools → Loop A (keep one rejected/accepted example if any) → 100 → fewer reviewed cases (publish the real count) → voice → UI polish.
**Never cut:** real Muse + MCP calls, validated drafts, safety gate, false-lesson rejection, raw-note baseline (Arm B), domain pack with leak test, reproducible logs.

## 6. Your time (human review)
| When | What | Time |
|---|---|---|
| Fri Oct 30 | Pilot data realism review | ~1 h |
| Sat Oct 31 | Approve/reject lessons in the Learning Lab (this is also demo footage) | ~30 min |
| Sun Nov 1 – Mon Nov 2 | Casebook review, 3 passes | 8–15 h, or a sample with an honest count |
| Tue Nov 3 | Record the video | ~3 h |

## 7. Credit budget (Meta $150 + Baseten)
| Item | Estimate |
|---|---|
| Spent so far | ~$24 |
| EXP-007 | ~$3 |
| Development runs (mostly mock) | ~$10 |
| Mining + Loop A probes | ~$10 |
| Final benchmark A–E × 100 × 2 | ~$40–60 |
| Hosted demo during judging | capped at ~$10 |
| Reserve | ≥ $20 |
