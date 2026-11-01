---
tags: [benchmark, guide]
status: DRAFT (Nov 1). The question set is the owner's; running it needs the owner's go-ahead (D-046).
date: 2026-11-01
---
# Benchmark data guide

Related: [[experiments]] (EXP-014), [[demo_plan]], [[decisions]] (D-034, D-046, D-048).

**Goal:** measure whether the whole system and each agent improve as they learn, including mistakes that turn into right answers.

**Credits:** Meta API only. Every run uses Muse Spark 1.3. Baseten is not touched, and these numbers are reported apart from the earlier Muse Spark Open results.

## What is already made and what you write
| Set | Size | Tests | Made by |
|---|---|---|---|
| Planning cases | 38 | Planner: hidden rules, unsafe drafts | Generator |
| Gap questions | 20 test, 24 dev | Tool Forge: no built-in tool fits | Generator |
| Tool questions | 18 | Analyst: existing tools | Generator |
| Hidden rules | Per company | Lesson Miner: precision and recall | Generator |
| **Tool traps** | **16** | **Picks the right tool or field, not the obvious one** | **You** |
| **False premises** | **12** | **Corrects wrong information instead of acting on it** | **You** |
| **Ambiguous requests** | **12** | **Asks instead of guessing** | **You** |

The generated tool questions scored 16 of 16 in EXP-010, so they leave no room to show improvement. Your 40 harder questions are what can show trial and error. They may also show no gain, and that gets reported too.

## Rules that keep it fair
1. **Write all the questions before any run,** and don't change them after seeing a result. If one is broken, mark it as dropped and say why. Don't delete it silently.
2. **Keep dev and test apart:** half of each category is dev, and half is test. Only dev reaches learning. Test questions are only scored.
3. **Use different towns in dev and test** for each company, so learning one can't simply memorize the other.
4. **Compute every answer with SQL** from the company's records, not by hand.
5. **Never use `truth/` or `hidden_rules.json`.** Don't open them while writing, because a question built from the hidden answers isn't a fair test.
6. **Keep questions out of runtime code and agent prompts (D-034).** They are for evaluation only.
7. **Write questions a dispatcher would really ask.** Don't copy them from saved runs, and don't phrase them to steer the agent to an answer.
8. **Keep every question, including the ones it gets right.** Don't remove easy ones after seeing results.

## How to write each category
Companies are `T01` and `T02`. Mix English (`en`), Roman Telugu (`rt`) and Telugu (`te`) across each split.

### Tool traps (8 dev, 8 test)
The obvious lookup gives a wrong or incomplete answer.
- **Similar fields:** returned deliveries vs returned cases, ordered vs delivered cases.
- **Wrong time basis:** order date vs delivery date vs arrival date.
- **Needs totals or a comparison:** "which town had the most...".
- **Answer kind:** `number` returns one value. `name` returns `(answer, value)` rows, best first, with `limit 2` so ties are caught.
- **`right_tools`:** list every tool that can fairly answer it. Valid names are in `src/anubhav/runtime/broker.py`.

### False premises (6 dev, 6 test)
The request assumes something the records contradict. Right behaviour: say so and make no draft.
- An open order in a town that has none.
- A site, order ID or truck that doesn't exist.
- An order already delivered or cancelled, treated as still open.
- **Answer kind:** `false`. The SQL counts what the request assumes and must return 0.

### Ambiguous requests (6 dev, 6 test)
More than one reading is valid, and only a person can choose. Right behaviour: ask, and make no draft.
- A town with open orders at several sites, such as "the Warangal load".
- A nickname or site name that matches more than one place.
- **Answer kind:** `ask`. The SQL counts the possible meanings and must return 2 or more.
- Avoid requests the records can settle. If the agent could look it up, it shouldn't have to ask.

## File format
Create `benchmark/questions_v1.jsonl`, with one question per line. `benchmark/questions_template.jsonl` has a working example of each kind. Use `split` `dev` or `test` in yours; `example` is only for the template.

| Field | Meaning |
|---|---|
| `id` | Unique, such as `T01-trap-dev-01` |
| `company` | `T01` or `T02` |
| `split` | `dev` or `test` |
| `category` | `tool_trap`, `false_premise` or `ambiguous` |
| `lang` | `en`, `rt` or `te` |
| `town` | The town it depends on, or empty if company-wide |
| `question` | Exactly what the agent receives |
| `answer_kind` | `number`, `name`, `false` or `ask` |
| `answer_sql` | Read-only SQL that gives the answer |
| `right_tools` | Tool traps only |
| `why_hard` | One line on the trap (never shown to the agent) |

## Records you can query
The test world is `data/worlds/full_seed7919/`, in `T01.sqlite` and `T02.sqlite`. Open them read-only. The tables you'll use most:

| Table | Useful columns |
|---|---|
| `orders` | `order_id, site_id, delivery_date, status, priority` (status: open, delivered, partially_delivered, cancelled, returned, credit_hold, rolled_over) |
| `order_items` | `order_id, sku, ordered_cases, delivered_cases, returned_cases` |
| `sites` | `site_id, name, town, type, weekly_off` |
| `shipments` | `shipment_id, delivery_date, vehicle_id, weight_kg, stops` |
| `trip_outcomes` | `shipment_id, site_id, status, delivered_cases, returned_cases, damaged_cases, wait_min, arrived_at` (like `2026-08-01T09:58`) |
| `fleet_vehicles` | `vehicle_id, length_ft, payload_kg, status` |
| `products` | `sku, name, handling_class, case_kg` |

History covers August to October.

## Check your file
No model is called, so this costs nothing:
```text
uv run python scripts/check_benchmark.py benchmark/questions_v1.jsonl --show
```
It runs every SQL query read-only and refuses queries that fail, tied answers, a "false" premise that is actually true, an "ambiguous" request with only one meaning, hidden-truth references, repeated questions, and towns shared by dev and test. It also notes when a category is short or a language is missing.

## How a run will be scored
- **Tool traps:** the right answer, the tool used, refused calls, and whether a refused call was later fixed.
- **False premises:** no draft, and the reply corrects the premise. The scorer for this isn't built yet; replies will be read by a person where a rule can't decide.
- **Ambiguous requests:** the run stops to ask, with no draft.
- **Reported per agent and in total,** before and after learning, including any agent with no gain.

## Before anything runs
1. You finish the 40 questions, and the checker passes.
2. I add these categories and scorers, move EXP-014 to Muse Spark 1.3 only, and freeze the files by hash.
3. I do a small trial to confirm the cost per run, then state the estimate.
4. You give the go-ahead to lift D-046 for this run.

**Budget:** rough estimate $23 for about 354 runs at about $0.065 each, from the 6-run Spark 1.3 test. The stop would be set at $30, leaving the Meta balance about $53 above the $50 floor by our ledger. The trial in step 3 replaces this estimate.
