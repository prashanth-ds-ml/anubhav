---
tags: [spec, data]
date: 2026-10-29
---
# Data spec v1: the Anubhavam demo world

What the generator builds, and why. It implements [[Data_Benchmark_Blueprint_v1.0]] at the D-027 scale (3 history companies + 1 new company). Status of each run: [[data_and_benchmark]]. Plan: [[build_plan]] Layer 1.

**Who we are modelling:** a **medium-sized regional 3PL** (third-party logistics company) in Telangana. It moves FMCG goods from brands' CFA depots (Carrying & Forwarding Agent warehouses) to distributors and stores. Its staff work in **Roman Telugu first, then Telugu script, then English**. It is not a national giant: no fancy TMS, plans live in a basic system plus people's heads and WhatsApp.

**Principles**
1. **World first.** Write the hidden truth (rules, nicknames, habits, events) *before* generating anything. Every trip, failure and note follows from it. Nothing is hand-placed.
2. **Real places, fictional businesses.** Towns, PIN codes and distances are real. Every company, person, vehicle number and phone number is invented.
3. **Messy on purpose.** EXP-007 showed that raw history is enough when it's small and clean. This world is large and noisy: stale notes, one-off failures, misleading habits, contradictions and look-alike sites. That is where governed lessons should earn their place.
4. **Reproducible.** One master seed, separate random substreams, versioned config, hashes for everything.
5. **Three layers: neat truth, messy evidence, neat lessons.**
   - *Truth* (hidden) is precise and structured, so every lesson can be checked. Example: "Lakshmi Agencies, Jangaon, north gate: max 22 ft".
   - *Evidence* (notes, trips, messages) is messy, as in real life, and only partly reveals the truth.
   - *Lessons* (Anubhavam's output) are structured again: scoped, evidenced, approved and expiring, so other planners and other companies can use them.

   Turning messy experience into usable knowledge is the product. It is never done by cleaning the evidence.

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

**Practitioner input (most important reference).** An interview on 2026-10-27 with a former logistics manager at a large FMCG company (anonymised; no names or quotes are published without permission):
- Orders reach the system from a sales app; allocation is already digital.
- **Truck/transporter planning is the pain:** about 1–1.5 hours per plan, up to ~10 re-plans a day in festival season.
- The real constraints (which truck fits where, which vendor is reliable) live in the planner's head.

The generator's daily rhythm, re-plan reasons and failure mix (§2) are built to reproduce this pain.

---

## 2. Scale and calendar
| Item | Value |
|---|---|
| History period | **90 days: 2026-08-01 → 2026-10-29** |
| Orders per day (weekday average) | T01 ≈ 9 · T02 ≈ 8 · T03 ≈ 14 |
| Total orders | ≈ **2,500–3,000** (trips emerge from consolidation; not fixed) |
| Sundays | ~30% of weekday volume |
| **Month-end rush** | Last 7–10 days of each month: ~1.4× orders (distributors push to meet sales targets) |
| Festival rush (Bathukamma/Dasara, Oct) | ~1.6× volume for the 10 days before; more re-plans, late trucks; some distributors closed on festival days |
| Monsoon weeks (Aug–mid Sep) | Higher delay and failure probability on rural roads |
| T-new | No history. Current state only (fleet, sites, today's orders) |

Volumes are config values. The pilot uses 7 days of T01 only.

### 2.1 Planning is driven by the delivery date and time
Every order carries a **requested delivery date and time window** (e.g. "Oct 14, 08:00–13:00" or "before 18:00"). The planner works **backwards** from it:

`latest dispatch time = window start − travel time − loading time − buffer`

| Order type | Typical window | When it is planned |
|---|---|---|
| Regular (most orders) | Next day, morning or by evening | Afternoon of the day before (D-1), after the noon order cut-off |
| Long-distance (Khammam, Karimnagar) | Next day | D-1 midday, dispatched in the evening |
| Urgent / top-up | Same day | Same morning, if a truck is free |
| Scheduled (modern trade, slot booking) | Fixed slot, e.g. 06:00–09:00 | D-1, with a hard slot |

**Daily rhythm:** orders arrive from 08:00 → noon cut-off → planning 12:00–16:00 → trucks report and load 16:00–21:00 → trips run overnight or next morning → deliveries and proof of delivery. Late orders after the cut-off, and anything that breaks the plan, trigger a **re-plan**.

### 2.2 Fleet mix
A mix that gives variety, as in real regional 3PLs:
| Type | Share | Behaviour |
|---|---|---|
| **Own trucks** | ~30% | Reliable, fixed drivers, maintenance days |
| **Attached vendor trucks** (regular transporters on contract) | ~50% | Usually reliable; each vendor has its own reliability and nicknames |
| **Market / spot trucks** (hired for the day) | ~20% | Used in rushes; higher rate; more no-shows and late reporting |

### 2.3 Why plans change (all realistic re-plan and failure reasons)
Each has a base rate in config, raised by rush periods, rain or a specific vendor/site. Some are pure noise; some come from hidden rules (§7).

| Group | Reasons |
|---|---|
| **Demand changes** | Late orders after cut-off · order quantity changed · order cancelled · urgent top-up order · distributor on **credit hold** (overdue payment) |
| **Stock** | Short stock at the depot → partial load or split · wrong SKU picked → return |
| **Truck supply** | Vendor **no-show** (truck promised, never placed) · truck **reports late** · wrong vehicle type sent · breakdown before or during trip · driver absent / driver change · truck rejected at loading (bad body, tarpaulin missing, dirty for food) |
| **Loading** | Loading delay at depot · overload caught at weighbridge → reload · documents missing (invoice, **e-way bill**) |
| **On the road** | Rain / waterlogging · road or bridge closure · traffic / city entry time restrictions · checkpost detention · accident · bandh / strike day |
| **At delivery** | Site access problem (truck too long for the gate/lane) · distributor godown full · distributor closed (holiday, festival) · receiving hours over → unload next morning · long unloading wait · partial acceptance · damage / short delivery claim · return of goods |
| **Cold chain (T03)** | Reefer not available · temperature breach → spoilage return |

**Re-plan count per day** is reported, so the demo can show the interview's pain (normal days: a few; festival days: up to ~10).

---

## 3. Geography (real places)

### 3.1 Towns, picked by business size
Towns come from a candidate list. The number of customer sites in each town is drawn at random, **weighted by the town's size and trade activity** (a tier, set from public population figures such as Census 2011, and whether it is a district headquarters or market town).

| Tier | Meaning | Site weight | Warangal-region candidates | Hyderabad-region candidates |
|---|---|---|---|---|
| 1 | Big city / trade hub | high | Warangal, Hanamkonda, Karimnagar, Khammam | Kukatpally, Secunderabad, Uppal, LB Nagar |
| 2 | District HQ / large town | medium | Kazipet, Jangaon, Mahabubabad, Siddipet, Suryapet, Jagtial | Medchal, Patancheru, Shamshabad, Gachibowli, Sangareddy |
| 3 | Small town / mandal market | low | Narsampet, Parkal, Bhupalpally, Huzurabad, Thorrur, Mulugu, Bhongir, Bhadrachalam | Bhongir, Ghatkesar, Shadnagar |

Some tier-3 towns get no site in a given company: that randomness is intended.

### 3.2 Corridors
Trucks run along real road corridors and can drop at several stops per trip:
Warangal → Jangaon → Bhongir · Warangal → Mahabubabad → Khammam · Hanamkonda → Parkal → Bhupalpally · Warangal → Huzurabad → Karimnagar · Warangal → Narsampet · Warangal → Thorrur → Suryapet. Hyderabad: city loops plus outbound to Sangareddy, Bhongir and Shadnagar.
Travel time = road distance at ~30–40 km/h on state roads, slower inside towns, plus gate waiting.

### 3.3 Sites
| Company | Customer sites | Shared with the other Warangal company |
|---|---|---|
| T01 | ~40–60 | ~25% of its sites (the big distributors) |
| T02 | ~40–60 | ~25% |
| T03 | ~80–100 | none (different region) |
| T-new | ~30–40 | ~25% with T01/T02's region |

Overlap is kept modest on purpose: enough that regional lessons matter, not so much that the companies look like copies.

**Site types:** old-town distributor godown (narrow lane) · highway-side warehouse (big yard) · modern-trade store (slots, dock height) · rural sub-stockist (small orders, bad roads in rain). Each site has one or more **entrances**, because rules live at the entrance level (PRD §9.3).

### 3.4 What is true vs what the company knows
This is the core of the world.

| | **True site profile** (hidden, `truth/`) | **What the company's system knows** (agent-visible) |
|---|---|---|
| Content | Gate/lane limits, dock height, receiving hours, weekly off, market day, parking, typical unloading wait | Name, address, town, PIN, phone, GSTIN-like ID, site type. Profile fields are mostly **empty** |
| How it is used | Decides trip outcomes in the simulation | What tools return |
| How the company learns more | — | Only through **driver notes, failed trips, staff edits and feedback** over time |

To keep it real, the system's site master is not perfectly empty or perfectly right:
- **~70%** of profile fields are blank at the start.
- **~20%** are filled and correct (things someone once typed in).
- **~10%** are filled but **outdated or wrong** (e.g. "receiving till 20:00" when it is now 18:00).

So the agent can't trust the master data blindly, and it has nothing to learn from on day 1. That is the gap Anubhavam's learning loop closes, and the reason T-new starts with only basic master data.

---

## 4. Businesses (fictional)
| ID | Company | Depot | Clients (shippers, fictional brands) | Fleet | Own nicknames |
|---|---|---|---|---|---|
| T01 | Warangal A (3PL) | Hanamkonda | 3 FMCG brands (oil, atta, biscuits, detergent) | ~14 vehicles (own + 3 attached vendors + spot) | yes |
| T02 | Warangal B (3PL) | Kazipet | 2 FMCG brands + 1 beverages | ~11 vehicles (own + 3 attached vendors + spot) | yes |
| T03 | Hyderabad (3PL) | Medchal | 4 brands incl. chilled dairy (needs reefer) | ~22 vehicles (own + 4 attached vendors + spot) | yes |
| T-new | New 3PL | Warangal area | 2 FMCG brands | ~9 vehicles (own + 2 attached vendors + spot) | yes |

Consignees are distributors, wholesalers and modern-trade stores. Some (e.g. the big Warangal and Jangaon distributors) are served by **both** T01 and T02. That overlap is what makes regional sharing meaningful.

### 4.1 What a medium regional 3PL looks like
- One depot next to its clients' CFA warehouses; 15–25 trucks managed (own + attached + spot).
- Small team: 1–2 planners, a supervisor, an accounts person; a driver pool of ~1.2× the trucks.
- Coordination over phone and WhatsApp with drivers, vendors and distributors. Planner messages and driver notes in the data look like these chats.
- 2–4 client brands per company.

### 4.2 Company personalities
| Company | Personality | Effect on the data |
|---|---|---|
| T01 | Old company; experienced senior planner | Many nicknames and shortcuts; lots of unwritten knowledge; the main learning story |
| T02 | Newer; staff write more formally | Fewer nicknames; more English; less written down about sites |
| T03 | Bigger, more systematic (Hyderabad) | More written policies and site rules; less to learn from notes; more volume |
| T-new | Just starting | Basic master data only; no history |

Each company has 2–3 planner personas with distinct writing styles: one types Roman Telugu, one Telugu script, one mostly English. The mix per company follows the staff preference order (§8).

### 4.3 Products and how they load
Each SKU has: case weight (kg), case volume (m³), max stacking height, temperature band, and a **handling class**.

| Handling class | Examples | Planning effect |
|---|---|---|
| Dense food | Edible oil, atta, rice, sugar | Truck fills on **weight** first ("weighs out") |
| Light / bulky food | Biscuits, snacks, noodles | Truck fills on **volume** first ("cubes out"); stacking limit (crushing) |
| Chemicals / home care | Detergent, toilet cleaner, soap | **Must not be loaded with food** (segregation) |
| Liquids / breakables | Beverages, glass bottles | Heavy; breakage claims; upright stacking |
| Chilled (T03 only) | Milk, curd, paneer | Reefer only; temperature band 2–8 °C (assumed) |

### 4.4 Genuine rules (real-world, public sources)
These are real Indian rules or standard industry practice. In the data they are **written** (visible to the agent through `written_policies` or document fields), so they test following rules, not learning them. Where a number depends on a state notification, the config value is an assumption, labelled as such.

| Rule | Source / basis | In the data |
|---|---|---|
| **E-way bill** required for goods movement above **₹50,000** consignment value | GST e-way bill rules | `eway_bills` table; missing or expired bill → checkpost detention |
| E-way bill **validity**: about 1 day per 200 km for normal cargo | GST e-way bill rules | Long trips that slip past validity need an extension |
| **No overloading** beyond the vehicle's permitted gross weight; fines at weighbridges | Motor Vehicles Act (overloading penalties), MoRTH axle-load norms | Overload → caught at weighbridge → reload/split |
| **Vehicle documents valid**: registration, fitness, permit, insurance, pollution certificate | Motor Vehicles Act | Expired document → vehicle can't be dispatched |
| **Food carried apart from chemicals**; clean, covered vehicles for food | FSSAI food-safety hygiene requirements | Segregation rule in loading; dirty/uncovered truck rejected at loading |
| **Lorry Receipt (LR) / consignment note** per consignment; signed copy as proof of delivery | Standard Indian road-transport practice | `proof_of_delivery` with LR number and signature status |
| **FEFO** (first expiry, first out) when picking stock | Standard FMCG warehouse practice | Picking order; wrong batch → return |
| **Last drop loaded first** on multi-drop trips | Standard loading practice | Load sequence per trip; wrong order → longer unloading |
| **Tarpaulin cover** for open trucks in rain | Standard practice | Rain + no tarpaulin → damage claim |
| **City heavy-vehicle entry hours** (Hyderabad) | Traffic police notifications (hours set in config) | Long trucks wait outside city limits during restricted hours |
| **Driver rest**: no driver beyond the company's daily duty limit | Company policy, based on motor transport labour rules | Driver availability; tired-driver reassignment |
| **Credit hold**: no dispatch to a distributor over its credit limit | Standard distributor practice | Orders on hold until payment |
| **Detention charges** after free unloading time | Standard transporter contract term | Long unloading waits cost money; shows up in vendor bills |

Hidden (unwritten) rules stay in §7. Written rules here are the **control**: the agent should follow them from the tools from day 1.

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

### 5.1 Body types
| Body | Share | Effect |
|---|---|---|
| **Open body** | most trucks (cheaper) | Needs a tarpaulin; in rain, light/bulky food (biscuits, snacks) should not go open-body |
| **Closed container** | ~30–40% of T14 and larger | Preferred for FMCG; higher rate |
| **Reefer** | T03 only | Dairy only |

### 5.2 Names planners actually use
Vehicle class labels in notes and messages follow trade slang: "Ace", "407", "Eicher", "14 feet", "19 feet", "22 feet" / "9 ton", "32 SXL" / "32 MXL", "container", "open bandi", "reefer". Plus company-private nicknames for specific trucks (H-05, H-07, H-24).

### 5.3 Each truck has a life
| Attribute | Purpose |
|---|---|
| Owner type: own / attached vendor / spot | Reliability, rate, GPS |
| Age (years) | Older trucks break down more often |
| Document expiry dates: fitness, permit, insurance, pollution | An expired document → can't be dispatched (§4.4) |
| Monthly maintenance day (own trucks) | Unavailable that day |
| GPS: own yes, attached some, spot no | Whether a live location exists in events |
| Registration number (fictional, TS-format) | Realistic IDs in notes |

Some documents expire **during** the 90 days, so availability changes over time. A few trucks are listed as "available" in the system while their documents have actually lapsed. That is a written-data check the agent should catch from the tools.

### 5.4 Real capacity can differ from paper capacity (hidden, learnable)
1–2 old trucks per company really carry **less than their paper payload**, because of a weak suspension or an old body. Example: a 32 MXL rated 15,000 kg that safely carries ~12,000 kg.
- **Evidence:** loads above the real limit get caught at the weighbridge or partially unloaded, with notes like "V12 lo 14 ton ekkadu, 2 ton digipoyindi" ("14 tons won't fit in V12; we offloaded 2 tons").
- **Correct outcome:** a private, truck-specific lesson ("V12: plan ≤ 12 t"), never shared (it's about that company's truck).
- Listed as hidden rules **H-14** (T01) and **H-25** (T03) in §7.

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
| H-14 | Real capacity (truck) | One old T01 32 MXL safely carries ~12,000 kg, not 15,000 | Weighbridge catches and partial offloads above ~12 t, with driver notes | Learn as a private truck lesson | **No** (T01 truck) |

### Hyderabad region
| ID | Kind | Truth | Planted evidence | Correct outcome | Shareable? |
|---|---|---|---|---|---|
| H-20 | Written rule (control) | City heavy-vehicle daytime restriction (written in `written_policies`) | Visible in tools | Follow it; nothing to learn | — |
| H-21 | Site access | Kukatpally modern-trade store: basement dock, max **T14** | T03 failures with T22 + notes | Learn | Hyderabad region only |
| H-22 | Cross-region alias clash | At T03, "Pedda godown" = **its own Medchal mega-warehouse** | T03 messages | Learn for T03; **must not** map to the Warangal site | — |
| H-23 | Cold chain | Dairy needs REEFER; one summer note says "ice boxes enough" | A non-reefer dairy trip has a spoilage return | Learn the rule; reject the shortcut | — |
| H-24 | Private aliases | T03 truck and vendor nicknames | T03 messages | Learn (T03) | **No** |
| H-25 | Real capacity (truck) | One old T03 T22 safely carries ~7,500 kg, not 9,000 | Weighbridge catches above ~7.5 t | Learn as a private truck lesson | **No** (T03 truck) |

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
- **Language mix (staff preference order):** ~50% Roman Telugu, ~30% Telugu script, ~20% English or mixed.
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
