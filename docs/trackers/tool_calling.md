---
tags: [tracker, tools]
---
# Tool-calling tracker

The 3PL MCP tools (PRD v3.1 §6.3) and how well Muse uses them. Failure patterns here feed Loop A in [[harness_versions]].
Old order-desk registry (40 tools): `archive/tool_calling_order_desk.md`

## 1. Tool registry
Every tool does real fixture-backed work. No dummy tools to inflate the count.

| # | Tool | Area | R/W | Contract test (A/B/C) | Examples EN/TE/RT/MIX | Status |
|---|---|---|---|---|---|---|
| 1 | list_shipments | Shipments | R | ⬜ | ⬜ | ⬜ |
| 2 | get_shipment | Shipments | R | ⬜ | ⬜ | ⬜ |
| 3 | list_vehicles | Vehicles | R | ⬜ | ⬜ | ⬜ |
| 4 | get_vehicle | Vehicles | R | ⬜ | ⬜ | ⬜ |
| 5 | check_vehicle_availability | Vehicles | R | ⬜ | ⬜ | ⬜ |
| 6 | get_site_constraints | Destinations | R | ⬜ | ⬜ | ⬜ |
| 7 | get_route_info | Destinations | R | ⬜ | ⬜ | ⬜ |
| 8 | create_dispatch_draft | Planning | W (draft) | ⬜ | ⬜ | ⬜ |
| 9 | get_dispatch_draft | Planning | R | ⬜ | ⬜ | ⬜ |
| 10 | cancel_dispatch_draft | Planning | W (draft) | ⬜ | ⬜ | ⬜ |
| 11 | record_driver_note | Outcomes | W (append) | ⬜ | ⬜ | ⬜ |
| 12 | list_trip_outcomes | Outcomes | R | ⬜ | ⬜ | ⬜ |
| 13 | get_transport_policy | Policy | R | ⬜ | ⬜ | ⬜ |

Add order/demand tools (orders, order items, allocation) only if Layer 1 needs them for planning tasks; log each addition here.

## 2. Tool-call observations
One row per notable call: good, bad or surprising.

| Date | run_id | Lang | Request snippet | Expected tool(s) | Actually called | Args OK? | Failure class | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

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
