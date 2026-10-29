"""Load the fictional business from datasets/business/*.csv into SQLite.

All brands, customers and prices are invented. CSVs hold rupees and percentages for easy
editing; the DB stores paise and basis points. datasets/business/hidden/ is never loaded:
it is shop knowledge the agent has to learn, not data it can look up.
Golden-path fixture: Ravi Traders (gold) asks for 12 cases of Godavari Gold Sunflower Oil 1 L;
8 cases are available across warehouses, so 4 are short; a restock lands 2026-11-02.
"""

import csv
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "datasets" / "business"


def rs(rupees: str) -> int:
    return round(float(rupees) * 100)


def pct(percent: str) -> int:
    return round(float(percent) * 100)


# table -> (csv file, columns in insert order, converters by csv column)
TABLES = {
    "customers": ("customers.csv", ["id", "name", "city", "tier", "active", "credit_status", "payment_terms",
                                    "credit_limit_rs", "outstanding_rs"], {"credit_limit_rs": rs, "outstanding_rs": rs}),
    "customer_aliases": ("customer_aliases.csv", ["customer_id", "alias", "script"], {}),
    "products": ("products.csv", ["sku", "name", "brand", "type", "variant", "category", "pack_size", "size_value",
                                  "size_unit", "units_per_case", "gst_rate_pct", "mrp_rs", "active"],
                 {"gst_rate_pct": pct, "mrp_rs": rs}),
    "product_aliases": ("product_aliases.csv", ["sku", "alias", "script", "kind"], {}),
    "units": ("units.csv", ["code", "name"], {}),
    "unit_aliases": ("unit_aliases.csv", ["unit_code", "alias", "script"], {}),
    "product_units": ("product_units.csv", ["sku", "unit_code", "pieces_per_unit"], {}),
    "warehouses": ("warehouses.csv", ["id", "name", "city"], {}),
    "inventory": ("inventory.csv", ["sku", "warehouse_id", "on_hand_cases", "reserved_cases"], {}),
    "restocks": ("restocks.csv", ["sku", "warehouse_id", "expected_date", "cases"], {}),
    "substitutes": ("substitutes.csv", ["sku", "substitute_sku"], {}),
    "prices": ("prices.csv", ["sku", "case_price_rs"], {"case_price_rs": rs}),
    "bulk_prices": ("bulk_prices.csv", ["sku", "min_cases", "case_price_rs"], {"case_price_rs": rs}),
    "customer_prices": ("customer_prices.csv", ["customer_id", "sku", "case_price_rs"], {"case_price_rs": rs}),
    "discount_rules": ("discount_rules.csv", ["tier", "discount_pct", "min_cases"], {"discount_pct": pct}),
    "schemes": ("schemes.csv", ["id", "sku", "buy_cases", "free_cases", "valid_from", "valid_to", "tiers",
                                "description"], {}),
    "policies": ("policies.csv", ["key", "value"], {}),
    "orders": ("orders.csv", ["id", "customer_id", "status", "created_at", "total_rs"], {"total_rs": rs}),
    "order_lines": ("order_lines.csv", ["order_id", "line_no", "sku", "cases", "case_price_rs"], {"case_price_rs": rs}),
}


def read_csv(name: str, data: Path = DATA) -> list[dict]:
    with open(data / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def seed(conn: sqlite3.Connection, data: Path = DATA) -> None:
    for table, (file, cols, conv) in TABLES.items():
        rows = [[conv.get(c, str)(r[c]) for c in cols] for r in read_csv(file, data)]
        conn.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})", rows)
