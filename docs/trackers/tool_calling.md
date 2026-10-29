---
tags: [tracker, tools]
---
# Tool-calling tracker

The 3PL MCP tools (PRD v3.1 §6.3) and how well Muse uses them. Failure patterns here feed Loop A in [[harness_versions]].
Old order-desk registry (40 tools): `archive/tool_calling_order_desk.md`

## 1. Tool registry
Every tool does real fixture-backed work. No dummy tools to inflate the count.
**Generic (D-030):** every tool works on the canonical model, so the same 16 tools serve all clients; contract tests run on T01 (schema A), T02 (B), T03 (C, tonnes) and TNEW. Built: `src/anubhav/runtime/broker.py`. Meta-tools `discover_capabilities` and `inspect_contract` expose each tool's manifest.
Status: ✅ = implemented and contract-tested on all 4 clients.

| # | Tool | Area | R/W | Contract test (A/B/C) | Examples EN/TE/RT/MIX | Status |
|---|---|---|---|---|---|---|
| 0a | discover_capabilities | Meta | R | ✅ | — | ✅ |
| 0b | inspect_contract | Meta | R | ✅ | — | ✅ |
| 0c | find_site | Sites | R | ✅ | ⬜ | ✅ |
| 1 | list_open_orders (was list_shipments) | Orders | R | ✅ | ⬜ | ✅ |
| 2 | get_order (was get_shipment) | Orders | R | ✅ | ⬜ | ✅ |
| 3 | list_vehicles | Vehicles | R | ✅ | ⬜ | ✅ |
| 4 | (get_vehicle merged into list_vehicles / check_vehicle_availability) | Vehicles | R | — | — | ✂️ |
| 5 | check_vehicle_availability | Vehicles | R | ✅ | ⬜ | ✅ |
| 6 | get_site_constraints | Destinations | R | ✅ | ⬜ | ✅ |
| 7 | get_route_info | Destinations | R | ✅ | ⬜ | ✅ |
| 8 | create_dispatch_draft | Planning | W (draft) | ✅ | ⬜ | ✅ |
| 9 | get_dispatch_draft | Planning | R | ✅ | ⬜ | ✅ |
| 10 | cancel_dispatch_draft | Planning | W (draft) | ✅ | ⬜ | ✅ |
| 11 | record_driver_note | Outcomes | W (append) | ✅ | ⬜ | ✅ |
| 12 | list_trip_outcomes | Outcomes | R | ✅ | ⬜ | ✅ |
| 13 | get_transport_policy | Policy | R | ✅ | ⬜ | ✅ |
| 14 | search_notes | Memory | R | ✅ | ⬜ | ✅ |

search_notes is the raw-memory baseline (Arm B): term-overlap search over notes, messages and feedback; results are marked untrusted text.

## 2. Tool-call observations
One row per notable call: good, bad or surprising.

| Date | run_id | Lang | Request snippet | Expected tool(s) | Actually called | Args OK? | Failure class | Notes |
|---|---|---|---|---|---|---|---|---|
| 10-29 | golden_path:rt/te/en/mix | all | "Jangaon Lakshmi load ki bandi pettu, confirm cheyyaku" | find_site, list_open_orders, get_site_constraints, list_vehicles, create_dispatch_draft | 8–9 calls incl. get_route_info, check_vehicle_availability ×2, get_transport_policy | ✅ | — | Day-1 mistake as designed: site constraints 'nothing recorded' → picks 32 ft T32M (V13/V14). Draft only; e-way bill warning surfaced |
| 10-29 | golden_path:te (1st) | TE | Telugu-script request | — | same | ✅ | multilingual-misread | Replied in Roman Telugu, and offered to 'dispatch on confirm' (it can't). Fixed in the system prompt (E-016); rerun replied in Telugu script, no offer |
| 10-29 | golden_path:ambiguous | RT | "Warangal load ki bandi pettu" | find_site / list_open_orders, then ask | find_site, list_open_orders | ✅ | — | Listed the 3 Warangal orders and asked which one; no guess |

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
