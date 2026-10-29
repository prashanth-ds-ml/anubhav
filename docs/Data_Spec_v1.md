---
tags: [spec, data]
date: 2026-10-29
---
# Data spec v1: the Anubhavam demo world

What the generator builds, and why. It implements [[Data_Benchmark_Blueprint_v1.0]] at the D-027 scale (3 history companies + 1 new company). Status of each run: [[data_and_benchmark]]. Plan: [[build_plan]] Layer 1.

**Principles**
1. **World first.** Write the hidden truth (rules, nicknames, habits, events) *before* generating anything. Every trip, failure and note follows from it. Nothing is hand-placed.
2. **Real places, fictional businesses.** Towns, PIN codes and distances are real. Every company, person, vehicle number and phone number is invented.
3. **Messy on purpose.** EXP-007 showed that raw history is enough when it's small and clean. This world is large and noisy: stale notes, one-off failures, misleading habits, contradictions and look-alike sites. That is where governed lessons should earn their place.
4. **Reproducible.** One master seed, separate random substreams, versioned config, hashes for everything.

---

## 1. Public references (structure and patterns only, no rows copied)
| Source | Verified (2026-10-29) | Licence | What we take |
|---|---|---|---|
| Amazon Last Mile Routing Research Challenge (AWS Open Data) | ✅ 9,184 routes; route-, stop- and package-level features | CC BY-NC 4.0 | Multi-stop trip shape, package size spread, stop counts |
| LaDe last-mile delivery dataset (Cainiao) | ✅ pickup + delivery CSVs, May–Oct 2022 | Research use (exact licence unconfirmed) | Event sequence and timing gaps: loaded → departed → arrived → unloaded → delivered |
| Olist Brazilian e-commerce (Kaggle) | ✅ page exists; tables and licence not confirmed | to confirm | Order → order item → product shape; late-delivery spread |
| India Post All India Pincode Directory | ✅ Department of Posts | GODL-India (reuse with attribution) | Real town names, districts, PIN codes |
| OpenStreetMap | known | ODbL (attribution) | Road distances between towns (or haversine × road factor as fallback) |
| Open Food Facts | known | ODbL | Realistic FMCG pack sizes and weights |
| GST e-way bill rule | public rule | — | E-way bill needed for consignments over ₹50,000 (a real document field and failure reason) |

Attribution for PIN codes, OSM and Open Food Facts goes in `LICENSES_AND_ATTRIBUTION.md`. Indian truck capacities, rates, site rules and outcomes are **our assumptions**, labelled as such.

---

## 2. Scale and calendar
| Item | Value |
|---|---|
| History period | **90 days: 2026-08-01 → 2026-10-29** |
| Orders per day (weekday average) | T01 ≈ 9 · T02 ≈ 8 · T03 ≈ 14 |
| Total orders | ≈ **2,500–3,000** (trips emerge from consolidation; not fixed) |
| Sundays | ~30% of weekday volume |
| Festival rush (Bathukamma/Dasara, Oct) | ~1.6× volume for the 10 days before; more re-plans, late trucks |
| Monsoon weeks (Aug–mid Sep) | Higher delay and failure probability on rural roads |
| T-new | No history. Current state only (fleet, sites, today's orders) |

Volumes are config values. The pilot uses 7 days of T01 only.

---

## 3. Geography (real places)
**Warangal region (T01, T02, T-new):** Warangal, Hanamkonda, Kazipet, Jangaon, Mahabubabad, Narsampet, Parkal, Bhupalpally, Khammam, Karimnagar, Siddipet, Bhongir.
**Hyderabad region (T03):** Kukatpally, Secunderabad, Uppal, LB Nagar, Medchal, Patancheru, Shamshabad, Gachibowli, plus outbound to Sangareddy and Bhongir.

Each consignee **site** has an address (fictional street + real town/PIN) and one or more **entrances** (north/south/main/back), because rules live at the entrance level (PRD §9.3).

---

## 4. Businesses (fictional)
| ID | Company | Depot | Clients (shippers, fictional brands) | Fleet | Own nicknames |
|---|---|---|---|---|---|
| T01 | Warangal A (3PL) | Hanamkonda | 3 FMCG brands (oil, atta, biscuits, detergent) | ~14 vehicles, 3 vendors | yes |
| T02 | Warangal B (3PL) | Kazipet | 2 FMCG brands + 1 beverages | ~11 vehicles, 3 vendors | yes |
| T03 | Hyderabad (3PL) | Medchal | 4 brands incl. chilled dairy (needs reefer) | ~22 vehicles, 4 vendors | yes |
| T-new | New 3PL | Warangal area | 2 FMCG brands | ~9 vehicles, 2 vendors | yes |

Consignees are distributors, wholesalers and modern-trade stores. Some (e.g. the big Warangal and Jangaon distributors) are served by **both** T01 and T02. That overlap is what makes regional sharing meaningful.

---

## 5. Vehicle classes (assumed, approximate public specs)
| Class | Typical model | Payload kg | Body length | Volume m³ |
|---|---|---|---|---|
| ACE | Tata Ace class | 750 | 7 ft | 3 |
| LCV407 | 407 class | 2,500 | 10 ft | 9 |
| T14 | 14 ft truck | 4,000 | 14 ft | 16 |
| T22 | 22 ft (9 MT) | 9,000 | 22 ft | 32 |
| T32S | 32 ft single axle | 7,500 | 32 ft | 55 |
| T32M | 32 ft multi axle | 15,000 | 32 ft | 55 |
| REEFER14 | 14 ft reefer (T03 only) | 3,500 | 14 ft | 14 |

Length, payload and volume are separate attributes. Site rules usually limit **length**; capacity limits **weight and volume**.

---

## 6. Canonical entity model
One canonical model; each company's database exposes it under its **own physical schema** (adapter variants, PRD §6.5).

| Area | Tables (canonical) |
|---|---|
| Parties | `shippers`, `consignees`, `sites`, `site_entrances` |
| Catalog | `products` (SKU, category, pack, case weight kg, case volume m³, temperature band) |
| Demand | `orders`, `order_items` (ordered / allocated / delivered / returned / cancelled qty) |
| Planning | `shipments`, `shipment_items`, `shipment_stops` |
| Resources | `vendors`, `vehicles`, `drivers`, `rate_cards`, `availability` |
| Execution | `trips`, `trip_events`, `trip_outcomes`, `proof_of_delivery`, `eway_bills` |
| Knowledge as written | `written_policies`, `site_access_rules` (**incomplete on purpose**) |
| Messy text | `planner_messages`, `driver_notes` (language, raw text, timestamp, linked trip) |

**Physical schemas:**
| Company | Variant | Example names |
|---|---|---|
| T01 | Adapter A | `fleet_vehicles`, `shipments`, `trip_notes`; weights in kg |
| T02 | Adapter B | `truck_master`, `loads`, `delivery_events`; weights in kg; IDs like `LD-2026-0412` |
| T03 | Adapter C | legacy `consignment_no`; weights in **tonnes** for loads, **cases** for items |
| T-new | random A/B/C from seed | |

**Invariants (checked by validators):** no orphan keys; allocated ≤ ordered − cancelled; shipment allocations reconcile to order items; delivered + returned traceable; no implicit unit mixing; payload and volume within class limits for every *delivered* trip; no vehicle or driver in two trips at once; notes never precede their event.

---

## 7. Hidden truth (draft for review)
Agent-invisible (`truth/hidden_rules.json`). Each rule lists the evidence the generator plants and what the right learning outcome is.

### Warangal region
| ID | Kind | Truth | Planted evidence | Correct outcome | Shareable? |
|---|---|---|---|---|---|
| H-01 | Site access | **Lakshmi Agencies, Jangaon, north entrance:** no vehicle longer than 22 ft | T01: 2 failed 32 ft trips (Aug 19, Sep 12) with driver notes; re-sends on T22 succeed. T02: 0 trips there before Oct | Advisory after the 1st failure; reviewer-approved policy after the 2nd | Yes (regional, site-specific) |
| H-02 | Look-alike site | **Sri Venkateswara Traders, Jangaon** (different site): no limit | Several successful 32 ft deliveries | H-01 must **not** spread to it | — |
| H-03 | Regional alias | "Pedda godown" = Venkata Sri Traders, Warangal (Mulugu Road) | Planners at T01 and T02 use it | Learn | Yes |
| H-04 | Regional alias | "Chowrasta load" = Sai Ganesh Agencies, Hanamkonda | Planner messages at T01 and T02 | Learn | Yes |
| H-05 | Private alias | "nalla lorry" = one T01 truck | T01 planner messages | Learn | **No** (T01 only) |
| H-06 | Private vendor alias | "Anna vallu" = T01's main vendor | T01 messages | Learn | **No** |
| H-07 | Private aliases | "pacha lorry" = one T02 truck; "Mama vallu" = a T02 vendor | T02 messages | Learn (T02) | **No** |
| H-08 | Habit trap | Khammam loads always go on T32M | Every Khammam trip is T32M (loads happen to be large); no failure on smaller trucks | **Reject** (habit, not rule) | — |
| H-09 | One-off failure | Sep 3 heavy rain: Narsampet road waterlogged | 2 failures that day, notes mention rain; all other Narsampet trips fine | **Don't** make it a rule | — |
| H-10 | Stale rule | Kazipet rail overbridge closed **Aug 1 → Sep 30**; detour adds ~40 min | August notes: "Kazipet bridge closed"; normal times from Oct 1 | Learn in Aug; **expire** after reopening | Yes, while valid |
| H-11 | Time window | Hanamkonda Chowrasta market area: no T22 or longer **09:00–20:00** | Daytime long trucks wait or fail; early/late ones succeed | Learn as time-scoped rule | Yes |
| H-12 | Contradiction | Mahabubabad, Ganesh Stores: one Aug note says "lorry lopaliki raadu" (truck can't get in), but 32 ft trucks deliver fine | 1 failure note (actually a driver error), then 4+ successes | Candidate → **challenged/rejected** | — |
| H-13 | Receiving hours | Venkata Sri Traders unloads only before 18:00 | "Unloaded next morning" notes for late arrivals | Learn (advisory) | Yes |

### Hyderabad region
| ID | Kind | Truth | Planted evidence | Correct outcome | Shareable? |
|---|---|---|---|---|---|
| H-20 | Written rule (control) | City heavy-vehicle daytime restriction (written in `written_policies`) | Visible in tools | Follow it; nothing to learn | — |
| H-21 | Site access | Kukatpally modern-trade store: basement dock, max **T14** | T03 failures with T22 + notes | Learn | Hyderabad region only |
| H-22 | Cross-region alias clash | At T03, "Pedda godown" = **its own Medchal mega-warehouse** | T03 messages | Learn for T03; **must not** map to the Warangal site | — |
| H-23 | Cold chain | Dairy needs REEFER; one summer note says "ice boxes enough" | A non-reefer dairy trip has a spoilage return | Learn the rule; reject the shortcut | — |
| H-24 | Private aliases | T03 truck and vendor nicknames | T03 messages | Learn (T03) | **No** |

### Everyone
| ID | Kind | Truth | Evidence |
|---|---|---|---|
| H-30 | Written policy | E-way bill required above ₹50,000 | Missing e-way bill → checkpost detention events |
| H-31 | Noise | Breakdowns, absent drivers, "godown full", partial deliveries, returns | Random at realistic rates; no pattern to learn |
| H-32 | Festival | October rush: more orders, more re-plans, more late trucks | Calendar-driven |

**T-new** sees the Warangal regional facts (H-01, H-03, H-04, H-11, H-13; H-10 already expired) and has its own private nicknames. The pack should help with the first group, must not include the second, and must not over-apply H-01 to H-02.

---

## 8. Messy text
- **Planner messages:** each trip has a planner message ("Pedda godown load ki nalla lorry pettu"). Nicknames appear at a realistic rate (30–60%), never 100%.
- **Driver notes:** on failures, delays and some normal trips. Example: "Jangaon godown north gate lo 32 adugula lorry tiragaledu, load venakki vachindi."
- **Language mix:** ~50% Roman Telugu, ~25% Telugu script, ~25% English or mixed.
- **Realism:** typos, missing details, wrong guesses by drivers (H-12), different spellings (Hanamkonda / Hanumakonda, Jangaon / Janagama).
- **Generation:** template families per event type, filled from truth and events. Muse may later paraphrase templates for variety, but **facts and labels always come from code**.
- **No oracle leaks:** a note may describe what happened, never the hidden rule ID, the "correct" answer or a test case.

---

## 9. Generator pipeline
| Step | Module | Output | Checks |
|---|---|---|---|
| 1 | `world` | Geography, companies, sites, entrances, products, vendors, vehicles, drivers, **hidden truth** | Unique IDs, valid scopes and dates |
| 2 | `demand` | Shippers' orders and items by calendar | Units, plausible weights, references |
| 3 | `shipments` | Allocation, consolidation, splits | Quantities reconcile; compatible products |
| 4 | `dispatch` | Vehicle and driver choice by a *planner model* (sometimes habitual, sometimes wrong) | Capacity, availability, no overlaps |
| 5 | `outcomes` | Events and outcomes from truth + noise | Chronology; failures explained by truth or noise |
| 6 | `notes` | Planner messages and driver notes | Language mix, no oracle leaks |
| 7 | `export` | Per-company SQLite in its physical schema + manifest | Adapter round-trip equals canonical |
| 8 | `validate` | Integrity report | **0 critical violations** or generation fails |

The **planner model** in step 4 matters: it imitates a human planner with habits (H-08), occasional mistakes and partial knowledge. That's how failures enter the history naturally.

**Seeds:** `master_seed` → substreams `geography`, `demand`, `resources`, `disruptions`, `notes`, `benchmark`. Changing the notes doesn't change the trips.

---

## 10. Output layout (git-ignored data, committed code and config)
```
configs/world_v1.yaml                 # all numbers in this spec
src/anubhavam/data/                   # generator modules (steps 1–8)
data/worlds/<run_id>/
  T01.sqlite  T02.sqlite  T03.sqlite  TNEW.sqlite   # agent-visible, per-company schema
  truth/hidden_rules.json             # NEVER agent-visible, never in MCP outputs
  truth/canonical.sqlite              # full canonical world for validators and the oracle
  manifest.json                       # seed, config hash, generator version, snapshot hashes
```

---

## 11. Done criteria
- **Pilot** (T01, Sep 8–14, ~60 orders, includes the Sep 12 Jangaon failure): 0 violations; you review 20 trips + 30 orders + the notes for realism.
- **Full run:** 90 days × T01/T02/T03 + T-new; 0 violations; same seed → same hashes; summary stats reviewed (orders/day, trips, failure rate by cause, language mix, nickname rates).
- Every H-rule has its planted evidence verifiably present (validator check).
