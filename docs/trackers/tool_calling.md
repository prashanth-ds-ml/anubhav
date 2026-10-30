---
tags: [tracker, tools]
---
# Tool-calling tracker

The 3PL MCP tools (PRD v3.1 §6.3) and how well Muse uses them. Failure patterns here feed Loop A in [[harness_versions]].
Old order-desk registry (40 tools): `archive/tool_calling_order_desk.md`

## 1. Tool registry
Every tool does real fixture-backed work. No dummy tools to inflate the count.
**Generic (D-030):** every tool works on the canonical model, so the same 27 tools serve all clients; contract tests run on T01 (schema A), T02 (B), T03 (C, tonnes) and TNEW.
**Categories (D-037):** tools are grouped by what a planner asks about; `discover_capabilities` returns them grouped. The action class (read / draft / append) still decides who may call what.

| Category | Tools | R/W |
|---|---|---|
| Orders & sites | find_site, list_sites, list_open_orders, get_order, get_site_constraints (one site), get_route_info | R |
| Fleet & drivers | list_vehicles (+ `available_on`), check_vehicle_availability (+ why not, workshop day), **list_drivers** | R |
| Planning | **plan_board** (whole day in one call), **check_load** (validate without creating), create_dispatch_draft, **create_dispatch_drafts** (batch), **list_dispatch_drafts**, get_dispatch_draft, cancel_dispatch_draft | R / W (draft) |
| Trips & documents | list_trip_outcomes, **trip_documents** (invoice, e-way bill, LR, POD, charges), record_driver_note | R / W (append) |
| History & performance | trip_history (+ vehicle filter), order_history, **performance** (on-time, fill, waiting, hired-truck late/no-show, charges; grouped) | R |
| Knowledge | get_transport_policy, search_notes (raw-memory baseline, Arm B), **list_lessons** (what it learned: rule / advice / waiting) | R |
| System | discover_capabilities, inspect_contract | R |

**Bold** = added 2026-10-30 after a user-question audit: "plan tomorrow" failed because the tools only looked at one order or site at a time, so 21 orders hit the 12-call limit.
EXP-008 to EXP-011 used the earlier 19-tool set; their results describe that version.

## 2. Tool-call observations
One row per notable call: good, bad or surprising.

| Date | run_id | Lang | Request snippet | Expected tool(s) | Actually called | Args OK? | Failure class | Notes |
|---|---|---|---|---|---|---|---|---|
| 10-29 | golden_path:rt/te/en/mix | all | "Jangaon Lakshmi load ki bandi pettu, confirm cheyyaku" | find_site, list_open_orders, get_site_constraints, list_vehicles, create_dispatch_draft | 8–9 calls incl. get_route_info, check_vehicle_availability ×2, get_transport_policy | ✅ | — | Day-1 mistake as designed: site constraints 'nothing recorded' → picks 32 ft T32M (V13/V14). Draft only; e-way bill warning surfaced |
| 10-29 | golden_path:te (1st) | TE | Telugu-script request | — | same | ✅ | multilingual-misread | Replied in Roman Telugu, and offered to 'dispatch on confirm' (it can't). Fixed in the system prompt (E-016); rerun replied in Telugu script, no offer |
| 10-29 | golden_path:ambiguous | RT | "Warangal load ki bandi pettu" | find_site / list_open_orders, then ask | find_site, list_open_orders | ✅ | — | Listed the 3 Warangal orders and asked which one; no guess |
| 10-30 | live check | TE | "రేపు orders కి నాకు ఒక ప్లాన్ ఇవ్వవా?" (T03, 21 orders) | plan_board, check_load, create_dispatch_drafts | plan_board, check_load ×2, create_dispatch_drafts, get_order ×3, list_dispatch_drafts | ✅ | — | Was: 13 calls, limit, no plan. Now 16 drafts, 18/21 orders, 3 reported left; $0.18 |
| 10-30 | live check | RT | "Repu anni orders ki plan cheyyi" (T01, lessons on) | plan_board, check_load, create_dispatch_drafts | exactly these 3 | ✅ | — | 10 drafts; learned 22 ft rule respected at Lakshmi; night-only site flagged |
| 10-30 | live check | RT | drivers who speak Telugu + phones; e-way/POD problems yesterday; on-time % and late vendors; "what have you learned?" | list_drivers; trip_documents; performance; list_lessons | same | ✅ | — | 1–3 calls each, $0.02 each |

**Failure classes:** retrieval-miss · wrong-tool · bad-args · multilingual-misread · sequencing · data-issue · policy-attempt · hallucinated-tool

## 3. Patterns by language (after the benchmark)
| Lang | Calls | Correct tool % | Correct args % | Top failure class |
|---|---|---|---|---|
| EN | | | | |
| TE | | | | |
| RT | | | | |
| MIX | | | | |

## 4. Known Muse facts (from Day 1, see [[smoke_tests]])
- `tool_choice` is `auto` only; we can't force a tool, so the graph and validator enforce order.
- `strict` validates the schema, not the arguments; validate arguments in code.
- Temperature/seed are not deterministic; repeat runs and report spread.
- Parallel tool calls are on by default.
