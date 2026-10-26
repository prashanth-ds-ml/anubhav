---
tags: [tracker, tools]
---
# Tool-calling tracker

How well Muse picks tools and fills in arguments. This is the main input for spotting failure patterns, and for the harness patches in [[harness_versions]].

## 1. Tool registry status
✱ = core tool (P0)

| # | Tool | Group | Core | R/W | Contract test | Examples EN/TE/RT | Status |
|---|---|---|---|---|---|---|---|
| 1 | find_customer | Customers | ✱ | R | ⬜ | ⬜ | ⬜ |
| 2 | get_customer_profile | Customers | ✱ | R | ⬜ | ⬜ | ⬜ |
| 3 | get_customer_terms | Customers | | R | ⬜ | ⬜ | ⬜ |
| 4 | get_customer_order_history | Customers | | R | ⬜ | ⬜ | ⬜ |
| 5 | check_customer_status | Customers | | R | ⬜ | ⬜ | ⬜ |
| 6 | search_products | Catalog | ✱ | R | ⬜ | ⬜ | ⬜ |
| 7 | get_sku_details | Catalog | ✱ | R | ⬜ | ⬜ | ⬜ |
| 8 | resolve_product_alias | Catalog | | R | ⬜ | ⬜ | ⬜ |
| 9 | get_pack_conversion | Catalog | ✱ | R | ⬜ | ⬜ | ⬜ |
| 10 | find_product_substitutes | Catalog | | R | ⬜ | ⬜ | ⬜ |
| 11 | check_stock | Inventory | ✱ | R | ⬜ | ⬜ | ⬜ |
| 12 | get_warehouse_stock | Inventory | | R | ⬜ | ⬜ | ⬜ |
| 13 | get_available_to_promise | Inventory | | R | ⬜ | ⬜ | ⬜ |
| 14 | get_restock_eta | Inventory | | R | ⬜ | ⬜ | ⬜ |
| 15 | get_stock_shortfall | Inventory | | R | ⬜ | ⬜ | ⬜ |
| 16 | get_standard_price | Pricing | ✱ | R | ⬜ | ⬜ | ⬜ |
| 17 | get_customer_price | Pricing | ✱ | R | ⬜ | ⬜ | ⬜ |
| 18 | get_bulk_price | Pricing | | R | ⬜ | ⬜ | ⬜ |
| 19 | get_discount_eligibility | Pricing | ✱ | R | ⬜ | ⬜ | ⬜ |
| 20 | get_tax_rules | Pricing | | R | ⬜ | ⬜ | ⬜ |
| 21 | create_draft_quote | Quotations | ✱ | W (draft) | ⬜ | ⬜ | ⬜ |
| 22 | get_draft_quote | Quotations | ✱ | R | ⬜ | ⬜ | ⬜ |
| 23 | revise_draft_quote | Quotations | | W (draft) | ⬜ | ⬜ | ⬜ |
| 24 | compare_quote_options | Quotations | | R | ⬜ | ⬜ | ⬜ |
| 25 | validate_quote | Quotations | ✱ | R | ⬜ | ⬜ | ⬜ |
| 26 | find_order | Orders | | R | ⬜ | ⬜ | ⬜ |
| 27 | get_order_status | Orders | | R | ⬜ | ⬜ | ⬜ |
| 28 | get_order_lines | Orders | | R | ⬜ | ⬜ | ⬜ |
| 29 | create_draft_order | Orders | | W (draft) | ⬜ | ⬜ | ⬜ |
| 30 | validate_order_draft | Orders | | R | ⬜ | ⬜ | ⬜ |
| 31 | get_delivery_slots | Fulfillment | | R | ⬜ | ⬜ | ⬜ |
| 32 | estimate_delivery_date | Fulfillment | | R | ⬜ | ⬜ | ⬜ |
| 33 | get_supplier_eta | Fulfillment | | R | ⬜ | ⬜ | ⬜ |
| 34 | check_allocatable_stock | Fulfillment | | R | ⬜ | ⬜ | ⬜ |
| 35 | get_fulfillment_policy | Fulfillment | | R | ⬜ | ⬜ | ⬜ |
| 36 | get_business_policy | Policies | | R | ⬜ | ⬜ | ⬜ |
| 37 | get_credit_policy | Policies | | R | ⬜ | ⬜ | ⬜ |
| 38 | get_returns_policy | Policies | | R | ⬜ | ⬜ | ⬜ |
| 39 | get_customer_outstanding | Policies | | R | ⬜ | ⬜ | ⬜ |
| 40 | summarize_quote | Policies | | R | ⬜ | ⬜ | ⬜ |

## 2. Tool-call observations
One row per notable call: good, bad, or surprising.

| Date | run_id | Lang | Request snippet | Expected tool(s) | Retrieved (top-k) | Actually called | Args OK? | Failure class | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 10-27 | smoke T2 | RT | "Ravi Traders ki … 12 cartons quote cheyyi" | find_customer, check_stock | all 3 (direct) | find_customer ∥ check_stock | ✅ | — | Parallel calls on the first turn |
| 10-27 | smoke T3 | TE | "రవి ట్రేడర్స్ కి … కోట్ చేయి" | find_customer, check_stock | all 3 (direct) | find_customer ∥ check_stock | ✅ | — | Telugu converted to Roman script in the args |
| 10-27 | smoke T4b | RT | "… Order confirm cheyyaku" | find_customer, check_stock, create_draft_quote; never confirm_order | 4 (direct) | the 3 expected | ✅ 3/3 | — | Negation honored |
| 10-27 | smoke T4b | RT | "… discount eligible aithe apply cheyyi" (not in prompt) | (get_discount_eligibility) | not offered | — | — | — | Reminder: discount needs its own tool; a likely retrieval-miss case later |
| 10-27 | smoke T5 | RT | same as T2 | find_customer, check_stock | 40 (direct) | find_customer ∥ check_stock | ✅ | — | Not distracted by 37 dummy tools |

**Failure classes:** retrieval-miss · wrong-tool · bad-args · multilingual-misread · sequencing · data-issue · policy-attempt · hallucinated-tool

## 3. Patterns by language (fill in after the benchmark)
| Lang | Calls | Correct tool % | Correct args % | Top failure class |
|---|---|---|---|---|
| EN | | | | |
| TE | | | | |
| RT | | | | |
| MIX | | | | |

## 4. Confusable tool pairs (good targets for harness patches)
| Pair | Why they get confused | Disambiguation hint added? |
|---|---|---|
| check_stock vs get_available_to_promise | | |
| get_standard_price vs get_customer_price vs get_bulk_price | | |
| search_products vs resolve_product_alias | | |
| create_draft_quote vs create_draft_order | | |
