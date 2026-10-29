"""Reference quote calculator: the business policies in code.

The verifier uses it to compute the correct quote for a task, and the quote tool will use the
same function, so there is one definition of "correct". Money is integer paise.
"""

import math
import sqlite3
from dataclasses import dataclass, field


@dataclass
class QuoteLine:
    sku: str
    cases: int
    free_cases: int
    scheme_id: str | None
    price_source: str
    case_price_paise: int
    discount_bp: int
    line_total_paise: int
    gst_paise: int
    available_cases: int
    shortage_cases: int
    note: str = ""


@dataclass
class Quote:
    customer_id: str
    allowed: bool
    lines: list[QuoteLine] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def subtotal_paise(self) -> int:
        return sum(line.line_total_paise for line in self.lines)

    @property
    def gst_paise(self) -> int:
        return sum(line.gst_paise for line in self.lines)

    @property
    def total_paise(self) -> int:
        return self.subtotal_paise + self.gst_paise


def business_date(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT value FROM policies WHERE key = 'business.date'").fetchone()[0]


def to_cases(conn: sqlite3.Connection, sku: str, quantity: float, unit: str) -> tuple[int, bool]:
    """Convert a quantity in any unit to whole cases, rounding up. Returns (cases, rounded)."""
    row = conn.execute(
        "SELECT pieces_per_unit FROM product_units WHERE sku = ? AND unit_code = ?", (sku, unit)
    ).fetchone()
    if row is None:
        raise ValueError(f"unit {unit!r} not valid for {sku}")
    upc = conn.execute("SELECT units_per_case FROM products WHERE sku = ?", (sku,)).fetchone()[0]
    exact = quantity * row[0] / upc
    cases = math.ceil(round(exact, 6))
    return cases, not math.isclose(exact, cases)


def _price(conn, customer_id: str, sku: str, cases: int) -> tuple[str, int]:
    row = conn.execute(
        "SELECT case_price_paise FROM customer_prices WHERE customer_id = ? AND sku = ?", (customer_id, sku)
    ).fetchone()
    if row:
        return "customer", row[0]
    row = conn.execute(
        "SELECT case_price_paise FROM bulk_prices WHERE sku = ? AND min_cases <= ? ORDER BY min_cases DESC LIMIT 1",
        (sku, cases),
    ).fetchone()
    if row:
        return "bulk", row[0]
    return "list", conn.execute("SELECT case_price_paise FROM prices WHERE sku = ?", (sku,)).fetchone()[0]


def _scheme(conn, sku: str, cases: int, tier: str, on_date: str) -> tuple[str | None, int]:
    for s in conn.execute(
        "SELECT * FROM schemes WHERE sku = ? AND valid_from <= ? AND valid_to >= ?", (sku, on_date, on_date)
    ):
        if s["tiers"] == "all" or tier in s["tiers"].split(","):
            free = cases // s["buy_cases"] * s["free_cases"]
            if free:
                return s["id"], free
    return None, 0


def _stock_note(conn, sku: str, shortage: int) -> str:
    parts = [f"short by {shortage} cases"]
    restock = conn.execute(
        "SELECT expected_date, cases FROM restocks WHERE sku = ? ORDER BY expected_date LIMIT 1", (sku,)
    ).fetchone()
    if restock:
        parts.append(f"restock of {restock['cases']} cases expected {restock['expected_date']}")
    sub = conn.execute("SELECT substitute_sku FROM substitutes WHERE sku = ?", (sku,)).fetchone()
    if sub:
        parts.append(f"substitute: {sub[0]}")
    return "; ".join(parts)


def compute_quote(conn: sqlite3.Connection, customer_id: str, lines: list[tuple[str, int]]) -> Quote:
    """Apply pricing, discount, scheme, stock and credit policies to (sku, cases) lines."""
    cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if cust is None:
        raise ValueError(f"unknown customer {customer_id}")
    if not cust["active"]:
        return Quote(customer_id, allowed=False, flags=["inactive_customer"])

    on_date = business_date(conn)
    hold = cust["credit_status"] == "hold"
    rule = conn.execute("SELECT * FROM discount_rules WHERE tier = ?", (cust["tier"],)).fetchone()
    quote = Quote(customer_id, allowed=True)

    for sku, cases in lines:
        product = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        if product is None:
            raise ValueError(f"unknown sku {sku}")
        source, price = _price(conn, customer_id, sku, cases)
        discount = 0
        if not hold and source != "customer" and rule["discount_bp"] and cases >= rule["min_cases"]:
            discount = rule["discount_bp"]
        gross = cases * price
        net = gross - round(gross * discount / 10_000)
        scheme_id, free = (None, 0) if hold else _scheme(conn, sku, cases, cust["tier"], on_date)
        available = conn.execute(
            "SELECT COALESCE(SUM(on_hand_cases - reserved_cases), 0) FROM inventory WHERE sku = ?", (sku,)
        ).fetchone()[0]
        shortage = max(0, cases + free - available)
        quote.lines.append(QuoteLine(
            sku=sku, cases=cases, free_cases=free, scheme_id=scheme_id, price_source=source,
            case_price_paise=price, discount_bp=discount, line_total_paise=net,
            gst_paise=round(net * product["gst_rate_bp"] / 10_000), available_cases=available,
            shortage_cases=shortage, note=_stock_note(conn, sku, shortage) if shortage else "",
        ))

    if hold:
        quote.flags.append("credit_hold")
    if cust["payment_terms"] != "cash" and cust["outstanding_paise"] + quote.total_paise > cust["credit_limit_paise"]:
        quote.flags.append("over_credit_limit")
    if any(line.shortage_cases for line in quote.lines):
        quote.flags.append("shortage")
    if any(line.free_cases for line in quote.lines):
        quote.flags.append("scheme_applied")
    return quote
