# ANUBHAV — DATA & BENCHMARK ENGINEERING BLUEPRINT

## Version 1.0 · 29 October 2026
**Companion to PRD v3.1 | Status: Implementation plan, not completed data**

## 1. Purpose and owner's design rationale

We are building a credible, inspectable testbed for a multilingual logistics agent that handles order-to-delivery work and improves planning, operations and tool use through independently verified experience. The owner specifically prefers **odd numbers**, hence **five** development-company databases. The number five is a deliberate product/design preference, not a statistical or industry requirement. Five also offers useful variety and geographic overlap without making the hackathon unmanageable. We do **not** rely on a single fixed sixth company: judges can seed and generate fresh cold-start tenants and unfamiliar orders. Preserve **two sealed benchmark packs**, a separate **development sandbox**, and a **live random-seed judge challenge**. Random demos demonstrate adaptability; sealed benchmarks demonstrate repeatable evidence.

## 2. Tenant portfolio and isolation

| ID | Fictional base | Operational emphasis | Schema variation |
|---|---|---|---|
| T01 | Hyderabad | Multi-customer FMCG, high order volume | Normalized order/shipment tables |
| T02 | Warangal A | Warehouses, entrance access, unloading delays | Legacy consignment identifiers |
| T03 | Warangal B | Different carriers, same regional corridors | Separate dispatch and carrier feeds |
| T04 | Vijayawada region | Multi-stop distribution and delivery windows | Route/stop-oriented records |
| T05 | Karimnagar | Agricultural/industrial products, seasonal demand | Inventory/weight-unit variation |

Use `tenant_01.sqlite` … `tenant_05.sqlite` for operational data. Separate `learning.sqlite` for tenant-scoped lessons, approvals, harness patches, regional packs and audit; `evaluation.sqlite` or immutable result JSONL for scored runs. **These are logical databases; five refers to the five company datasets**, not the total number of internal SQLite files. Each tenant has independent identifiers, authorization, historical data and an MCP adapter that normalizes to the same typed capability contract. Never join tenant databases in an agent-accessible query.

## 3. Sources and provenance

Use **Olist** as an orders/items/products relational reference; **Amazon Last Mile Routing Research Challenge** for route/stop/package/time-window shapes; **LaDe** for task/event sequences. Their data are not a complete Indian 3PL model. Record source URLs, license/usage restrictions, extraction date, field mapping and what was *inferred*. Prefer schema/distribution inspiration rather than copying foreign operational records. All fictional Indian routes, traffic, rates, site restrictions and delivery outcomes are **synthetic**, unless separately verified. Do not claim real-world empirical validity from simulation alone.

## 4. Canonical entity model

### 4.1 Demand and provenance

`customers(customer_id, tenant_id, customer_type, service_tier)`; `sites(site_id, location_id, entrance_id, site_type, operating_windows)`; `products(product_id, category, sku, unit_of_measure, net_kg_per_unit, gross_kg_per_unit, cubic_m_per_unit, temperature_band, hazard_class, stackability)`; `orders(order_id, tenant_id, customer_id, created_at, pickup_site_id, delivery_site_id, due_start, due_end, status, channel)`; `order_items(order_item_id, order_id, product_id, ordered_qty, uom, unit_weight_kg, allocated_qty, delivered_qty, cancelled_qty)`; `shipments(shipment_id, tenant_id, status, pickup_window, delivery_window)`; `shipment_items(shipment_id, order_item_id, allocated_qty)`; `shipment_stops(shipment_id, sequence, site_id, stop_type, planned_window)`.

**Invariants:** no orphan keys; nonnegative quantities; `allocated_qty <= ordered_qty - cancelled_qty`; sum of shipment allocations reconciles to order-item allocations; delivered plus returned quantities are traceable; no implicit mixing of kg, tonnes, cartons and pallets; gross payload and volume include packaging. A single order may split across shipments; a shipment may combine items from multiple orders if compatible.

### 4.2 Resources and outcomes

`carriers`, `carrier_contracts`, `carrier_rate_cards`, `vehicles` (ownership/contract status, payload, cube, dimensions), `drivers`, `availability_windows`, `assignments`, `resource_reservations`, `routes`, `route_stops`, `trip_events`, `trip_outcomes`, `driver_notes`, `exceptions`, `proof_of_delivery`, `written_policies`, `site_access_rules`. Include valid-from/to and recorded-at times for changing facts. Enforce booking conflicts atomically at DB level/transaction boundary; do not trust LLM text for safety checks.

### 4.3 Learning, transfer and evaluation

`lesson_candidates`, `lesson_evidence`, `lesson_reviews`, `approved_lessons`, `lesson_events`, `harness_proposals`, `harness_probe_results`, `harness_versions`, `domain_pack_publications`, `share_approvals`, `revocations`, `agent_runs`, `tool_calls`, `planning_runs`, `plan_candidates`, `plan_outcomes`, `audit_events`, `benchmark_manifests`, `benchmark_results`. Store provenance, scope (site/entrance/route/product/vehicle/time), counterevidence, reviewer, approval, expiry, version and tenant. A candidate is not a policy. A shared pack must not contain customer-level transactions, private rates, driver identifiers or sensitive low-sample aggregates.

## 5. 90-day synthetic world generation

**World-first principle:** define hidden true constraints and distributions before generating the evidence or benchmark questions. Generate: geography/service areas → tenants/sites → customers/products/carriers/vehicles → hidden rules with validity periods → daily order demand → order items and quantities → feasible/infeasible dispatch situations → trip events/outcomes → multilingual notes and human corrections → future evaluation tasks.

Use distinct seeded RNG substreams (`geography`, `demand`, `resources`, `disruptions`, `notes`, `benchmark`) and record `master_seed`, generator Git commit/version, config JSON hash and DB snapshot hash. Generate weekends, weekday seasonality, peak orders, cancellations, repeat customers, changing carrier availability, multi-stop routes, temperature-sensitive cargo, incompatible products, partial fulfillment and realistic missing information. Inject both **true recurring patterns** and **misleading correlations**; include stale rules, contradictory observations and site-specific negative controls. Never make every note directly state the hidden answer.

**Provisional scale:** 90 days across five development tenants, approximately 2,000–3,000 orders, configurable products, sites, fleet and carrier sizes. Trip counts should *emerge from consolidation/splitting*; don't hardcode a trip total that contradicts demand. Generate a small pilot first (e.g. 7 days, 2 tenants, 100 orders) and validate it before scaling.

## 6. Script plan and reproducible build order

| Script | Responsibility | Required checks |
|---|---|---|
| `01_generate_world.py` | Tenants, sites, product catalog, hidden rules | Unique IDs, scope, temporal validity |
| `02_generate_demand.py` | Customers, orders, item quantities | Unit conversion, plausible weights, references |
| `03_build_shipments.py` | Allocate, consolidate/split loads | Allocation conservation, compatibility |
| `04_simulate_dispatch.py` | Carriers, vehicles, drivers, trips | Capacity, availability, atomic conflicts |
| `05_simulate_outcomes.py` | Events, delivery, failures, delays | Chronology, reproducible outcome functions |
| `06_generate_notes.py` | English/Telugu/Roman Telugu evidence | Source/time metadata, noise, no oracle leak |
| `07_build_casebook.py` | Sample tasks, private oracle, splits | Family/time isolation, negative controls |
| `08_validate_all.py` | SQL + Python integrity tests | Zero critical invariants violated |
| `09_review_export.py` | Reviewer packets and manifests | Agent/oracle separation, versioning |
| `10_run_benchmarks.py` | Paired A/B/C/D and optional transfer | Same snapshots, budgets, safety, metrics |

Recommended stack: Python, SQLite, Pydantic, Faker (synthetic names), NumPy random generators, OR-Tools for small optimization instances, Pytest, Pandas for audit reports, Streamlit for review UI. Pin dependencies and store scripts/config in Git. Synthetic Telugu notes may be assisted by Muse, but facts and labels must come from deterministic world truth and manual review.

**CLI examples (planned interfaces, not implemented commands):**

```bash
python scripts/01_generate_world.py --seed 20261104 --config configs/pilot.yaml
python scripts/02_generate_demand.py --seed 20261104 --days 90
python scripts/08_validate_all.py --manifest data/manifests/run_20261104.json
python scripts/07_build_casebook.py --seed 104729 --sealed-count 100
pytest tests/data_integrity tests/safety tests/benchmark
```

## 7. Validation and quality gates

**Structural:** foreign keys, uniqueness, tenant ownership, no duplicate order-item allocations, valid enum/unit types, nonnegative amounts. **Temporal:** `order_created <= pickup <= delivery`, note creation cannot precede its source event, no future evidence in earlier tasks, effective dates respected. **Physical:** mass, cube, dimensions, temperature and compatibility; site entrance and vehicle constraints. **Operational:** driver/vehicle overlap, idempotency, capacity, realistic service windows, at least one feasible candidate where a task expects a plan. **Statistical:** distribution summaries by tenant, product, carrier, time, language, outcome and route; inspect extreme outliers and class balance. **Privacy:** tenant read denials, pack approval, revocation, redaction and no hidden oracle in MCP outputs. **Reproducibility:** same seed/config/version gives identical canonicalized output hashes; different seeds change meaningful case features without breaking invariants.

Automate property-based tests, adversarial boundary cases (capacity exactly at limit, one kilogram over, overlapping holds, changed quantities, unavailable carrier), independent optimizer checks and a leakage scan for private oracle IDs/labels in agent-visible fixtures. Fail generation rather than silently repair an invalid benchmark case.

## 8. Exactly 100 human-reviewed sealed benchmark cases

Two **50-case** packs:

| Pack | Category | Count |
|---|---|---:|
| 1 — Operational competence | Orders, quantity and units | 10 |
| 1 | Consolidation, splitting, planning | 15 |
| 1 | Carrier, vehicle and driver choice | 10 |
| 1 | Dispatch exceptions and replanning | 10 |
| 1 | Multilingual tool/intent execution | 5 |
| 2 — Learning and transfer | True, false, stale and conflicting lessons | 15 |
| 2 | Harness/tool-use improvement | 10 |
| 2 | Permissioned regional transfer/cold-start | 15 |
| 2 | Cross-task multilingual application | 10 |
| **TOTAL** | | **100** |

Language, tenant, difficulty and safety are **cross-cutting tags**, not extra counted tasks. Deliberately balance English, Telugu, Roman Telugu and code-mixed cases. Add a separate automated adversarial suite for concurrency, injection, authorization, rollback and leakage. Include tasks with no feasible plan, legitimate clarification, multiple valid solutions and cases where the right learning outcome is **reject**.

**Do not let the agent or learning proposer read** `oracle_private/`, scoring source, future outcomes or sealed case labels. Split by scenario family, route/site combinations and time; keep a separate development pool and improvement-probe set. Freeze sealed case IDs, inputs, fixture hashes, evaluation code and reviewer decisions before final runs. A generated seed is reproducible, not necessarily independent of training templates: inspect family overlap.

## 9. Human review procedure — weekend plan

**Pass 1 — realism and provenance:** review all world rules, customer/product/site assumptions, 30 orders and 20 trip histories; check whether quantities, routes and operational events make sense. Prefer a logistics practitioner's review of 10–15 difficult examples when feasible. **Pass 2 — oracle correctness:** review every one of the 100 sealed case manifests; independently recompute 15–20 planning cases; mark exact, multiple-valid, infeasible or clarification-required outcomes. **Pass 3 — final adjudication:** verify all 100 for ambiguity, Telugu/Roman Telugu semantics, tenant permissions, scenario leakage, negative controls and scoring rubric. Track reviewer ID, date, revisions, confidence, evidence and unresolved disagreement. Reviewers should be blind to agent outputs when writing initial oracle verdicts; later audit model failures separately. If 100 cannot be reviewed well, publish the actual smaller reviewed set honestly.

**Suggested time:** Weekend 1: 6–8 hours for realism and source rules. Weekend 2: 8–12 hours for casebook, language, oracle and leakage. Add an independent second reviewer for ambiguous or high-risk cases when possible; do not claim independent dual review unless it happened.

**Review labels:** `approved`, `needs_revision`, `rejected`, `ambiguous_multiple_valid`, `requires_clarification`; record why and preserve revision history. The reviewer-facing manifest references a private oracle by ID but does not embed it in agent-visible task JSON.

## 10. Scoring and before/after learning experiments

Four matched arms: **A** baseline structured data + MCP; **B** A + raw historical note retrieval; **C** B + approved evidence-backed lessons (same retrieval access); **D** C + approved bounded harness patches. Optional transfer experiment: D with/without authorized regional pack for a new tenant. Run all arms on identical frozen task snapshots, deterministic world conditions, optimizer, safety verifier, model configuration and tool budgets; random provider variation should be repeated and reported, not concealed. Historical evidence for learning is separate from sealed evaluation. Compare paired case-by-case differences and uncertainty; show denominators.

**Primary metrics:** verified task success; feasible-plan rate; valid-plan cost gap vs exact optimum or documented solver bound; on-time outcomes; tool validity; lesson precision/recall and false promotion; approved regional-transfer uplift and false transfer; critical safety violations; cross-tenant leaks; latency, tokens and dollar cost per successful task; regression rate. Report rejected proposals and null/negative improvements. Safety violations are a release gate, not a score that can be traded for cheaper plans.

## 11. Live judge random-seed challenge

Judge chooses **seed, 1–3 new tenants, order count (e.g. 5–100), difficulty and scenario family**. Generator creates an unfamiliar but valid world, snapshots it, displays the manifest hash, and sends only authorized records and requests through tenant MCP adapters. Show a **sanitized observable timeline** for Planning, Operations and Experience: goal, selected tool, inputs/outputs, evidence, constraints, draft alternatives, verifier, human approval, lesson candidate, probes, approval and measured effect. Never display fabricated private chain of thought. Provide one-click replay with same seed, plus a **different seed** challenge. Clearly mark this as exploratory live evaluation, not a substitute for sealed results. Do not train from judge-test outcomes before scoring that same challenge.

## 12. Knowledge transfer and cold-start controls

The new tenant can use only approved and eligible regional/site/route packs. Publishing requires authorized source approval, scope, minimum evidence, privacy review, expiry and revocation; receiving requires tenant authorization. Prefer exact site/entrance matching over city-wide inference. Include matched tests: same site/new client; same corridor/new carrier; same city/different site (must **not** transfer site-specific rule); revoked/expired pack; contradictory local evidence. Never expose customer prices, shipment volumes, driver identity or private contracts. Transfer is a product hypothesis to test, not proven network effect.

## 13. Repository and data access boundaries

```text
anubhav/
  configs/                     # generator scenarios, versions, source manifest
  scripts/                     # 01..10 generation, checks, review, evaluation
  app/agent/                   # shared Muse runtime and three logical workflows
  app/mcp/                     # registry and per-tenant adapters
  app/safety/                  # independent checks, reservations and approvals
  app/learning/                # two loops, pack publishing and revocation
  data/dev/                    # five synthetic company databases
  data/sandbox/                # disposable seeded development worlds
  data/manifests/              # seed, config, schema, snapshot hashes
  benchmarks/dev/              # development and probe cases
  benchmarks/sealed/           # restricted frozen evaluation inputs
  benchmarks/oracle_private/   # NEVER deploy or commit publicly
  benchmarks/results/          # reproducible paired runs and sanitized exports
  tests/                       # integrity, properties, privacy, concurrency
  docs/                        # dictionary, provenance, review and limitations
```

Public demo deployments must not contain hidden oracle files, scoring keys or sensitive reviewer-only annotations. Prefer a private evaluation runner and a sanitized public report. Maintain versioned snapshots and a reproducibility manifest for every published metric.

## 14. Build gates and fallback scope

**Gate 1:** small pilot generates with zero integrity violations. **Gate 2:** five tenant adapters pass the same MCP contract tests. **Gate 3:** planning and operations produce only independently verified drafts. **Gate 4:** candidate lessons and harness patches pass review, probes and regression tests. **Gate 5:** 100-case sealed casebook passes human review, or explicitly publish a smaller validated denominator. **Gate 6:** live seed challenge replays identically and does not leak hidden truth. **Gate 7:** final A/B/C/D and cold-start comparison is rerunnable from manifests.

If hackathon time is tight, prioritize one end-to-end verified planning-and-learning example, strong integrity checks, two representative tenant adapters and a smaller fully reviewed sealed suite. Five company datasets can still be generated, but never claim full adapter/benchmark coverage if not implemented.

## 15. Open risks and honest limitations

Synthetic outcomes are only as realistic as the generator assumptions. Public routing/order datasets do not establish regional Indian truck constraints. Reviewer bias and overlapping scenario templates can inflate scores. LLM outputs may vary despite fixed seeds; report repeats. Simulated savings are not real business ROI. A generated new tenant is not equivalent to an independently sourced real customer. More agents can increase complexity and cost; compare three specialist workflows with a one-generalist baseline. The benchmark is credible when it documents these limits and publishes failures alongside successes.
