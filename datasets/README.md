# Datasets

Everything here is **fictional**: brands, customers, prices and stock are invented for a Telugu-speaking FMCG/kirana distributor in Andhra Pradesh. The business date is fixed at **2026-10-28** (`policies.csv`), so every run sees the same world.

## `business/`: the distributor's ERP, as CSV
The CSVs are the source of truth. `uv run python scripts/data/build_db.py` loads them into `data/business.db` (SQLite, gitignored). CSVs hold rupees and percentages; the DB stores paise and basis points.

| File | Rows | What it holds |
|---|---|---|
| `products.csv` | 84 | SKUs with brand, type, variant, pack size, units per case, GST, MRP. Several SKUs share a type (7 sunflower oils), so lookups are genuinely ambiguous |
| `product_aliases.csv` | 523 | Names in English, Telugu script and Roman Telugu (`generic`, `brand`, `pack`) |
| `units.csv`, `unit_aliases.csv` | 7, 35 | case/petti, piece/packet, dozen, kg, litre, bag/bastha, tin/dabba |
| `product_units.csv` | 348 | Pieces per unit for each SKU (e.g. 1 kg of a 500 g pack = 2 pieces) |
| `customers.csv`, `customer_aliases.csv` | 17, 37 | Tier, credit status, terms, limit, outstanding. Includes look-alike names (Ravi ×2, Lakshmi ×2, Sai ×2), one inactive and one credit-hold customer |
| `prices.csv`, `bulk_prices.csv`, `customer_prices.csv` | 84, 7, 4 | List, bulk and negotiated case prices |
| `discount_rules.csv` | 3 | Tier discount and minimum cases |
| `schemes.csv` | 4 | Trade schemes (buy N get M free), one tier-restricted, one expired |
| `inventory.csv`, `restocks.csv`, `substitutes.csv` | 168, 4, 14 | Stock in two warehouses, incoming restocks, substitutes |
| `orders.csv`, `order_lines.csv` | 98, 245 | Aug–Oct 2026 order history, so "same as last time" and default sizes are answerable |
| `policies.csv` | 14 | The business rules in plain words. `src/order_agent/pricing.py` implements them |

## `business/hidden/`: shop knowledge the ERP doesn't have
`shop_slang.csv` holds what the owner and staff know but the system doesn't: "GG oil", "pedda dabba" (the 15 L tin), "pacha sabbu" (neem soap), "Ravi anna" (Ravi Traders, not Ravi Kumar Provisions). It is **never loaded into the DB** and never shown to the agent. A test enforces this.

This is the headroom for the "learns through verified experience" claim: a frozen model can't know a shop's private slang, so the baseline fails those tasks. Approved harness patches (aliases, guidance) can fix them. The file is the answer key for grading, not an input.

## `tasks/benchmark_v1.jsonl`: 48 tasks
- **Split:** 32 dev, 16 locked held-out. **Languages:** 8 English, 12 Telugu script, 16 Roman Telugu, 12 mixed (PRD §11).
- **Actions:** `quote` (40), `clarify` (5: ambiguous customer or product), `no_quote` (3: inactive customer). **Slang tasks** (need hidden shop knowledge): 9 (6 dev, 3 held-out).
- **Coverage tags:** golden, shortage, substitute, discount, bulk, customer_price, scheme, scheme_expired, credit_hold, credit_limit, inactive, units, negation, correction, history_default, history_repeat, customer_ambiguity, product_ambiguity, slang, multi_item.
- `expected.flags` and `expected.total_paise` are computed by the pricing engine, not by hand. `tests/test_benchmark.py` re-checks every task against the data: flags, totals, forbidden items, real ambiguity, history defaults, and that hidden terms really are hidden.

A task passes when the agent's draft quote has exactly the expected `(sku, cases)` lines and flags, contains nothing forbidden, and uses the right customer. For `clarify` and `no_quote`, it passes when no quote is created and the operator is told why.
