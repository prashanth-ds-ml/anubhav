"""The distributor's 40 business tools: one registry, exported as Chat Completions tools (arm A)
or as Responses API namespaces with deferred loading for Muse tool search (arm B).

Every tool is a plain function of (conn, **args) that returns JSON-able data. Pricing comes from
pricing.compute_quote, never from the model. Writes are draft quotes only: nothing confirms,
dispatches or sends.
"""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable

from .pricing import compute_quote, to_cases


@dataclass(frozen=True)
class Tool:
    name: str
    namespace: str
    description: str
    parameters: dict
    fn: Callable
    writes: bool = False


NAMESPACES = {
    "customers": "Retailer (customer) lookup: names and aliases, profile, tier, credit status and balances.",
    "catalog": "Product catalogue: search SKUs by name, brand, type, pack or Telugu / Roman-Telugu alias; SKU details, GST, MRP.",
    "units": "Units and packs: petti/case, packet/piece, dozen, kg, litre, bastha/bag, dabba/tin; convert quantities to cases.",
    "stock": "Warehouse stock, availability, restock dates and substitutes.",
    "pricing": "Prices and offers: list, bulk and customer-specific prices, tier discounts, trade schemes, quote preview.",
    "orders": "Past orders: history, last order, order details and status, a customer's usual products.",
    "quotes": "Draft quotations: create, read, list, update and discard drafts. Drafts only; never confirms orders.",
    "policy": "The distributor's business policies and rules.",
}

S = {"type": "string"}
I = {"type": "integer", "minimum": 1}
LINES = {"type": "array", "items": {"type": "object", "properties": {"sku": S, "cases": I}, "required": ["sku", "cases"]}}


def params(required=(), **props):
    return {"type": "object", "properties": props, "required": list(required)}


# Filler words in requests that say nothing about which customer or product is meant.
FILLER = {"shop", "ki", "ku", "kosam", "garu", "కి", "కు", "షాప్", "గారు", "the", "for", "to"}


def _tokens(text: str) -> list[str]:
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text.lower())  # "200g" -> "200 g", "1l" -> "1 l"
    return [t for t in re.split(r"[\s,.;:!?()/|&-]+", text) if t and t not in FILLER]


def _score(query: str, hay: str) -> int:
    """Query words that match a word in hay (whole word, or a prefix of 3+ letters)."""
    words = set(_tokens(hay))
    return sum(any(w == t or (len(t) >= 3 and w.startswith(t)) for w in words) for t in _tokens(query))


def _rs(paise: int) -> float:
    return paise / 100


def _product(conn, sku):
    row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if row is None:
        raise ValueError(f"unknown sku {sku}")
    return row


def _customer(conn, customer_id):
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown customer {customer_id}")
    return row


def _brief(p):
    return {"sku": p["sku"], "name": p["name"], "pack_size": p["pack_size"], "units_per_case": p["units_per_case"]}


# ---------- customers
def find_customer(conn, query):
    found = []
    for r in conn.execute("SELECT c.*, group_concat(a.alias, ' | ') AS aliases FROM customers c "
                          "LEFT JOIN customer_aliases a ON a.customer_id = c.id GROUP BY c.id"):
        score = _score(query, f"{r['name']} | {r['aliases']}")
        if score:
            found.append((score, {k: r[k] for k in ("id", "name", "city", "tier", "active", "credit_status")}))
    best = max((sc for sc, _ in found), default=0)
    return [c for sc, c in found if sc == best][:6]  # only the best-matching candidates


def get_customer_profile(conn, customer_id):
    c = dict(_customer(conn, customer_id))
    c["credit_limit_rs"], c["outstanding_rs"] = _rs(c.pop("credit_limit_paise")), _rs(c.pop("outstanding_paise"))
    c["aliases"] = [r[0] for r in conn.execute("SELECT alias FROM customer_aliases WHERE customer_id = ?", (customer_id,))]
    return c


def get_credit_status(conn, customer_id):
    c = _customer(conn, customer_id)
    return {"customer_id": customer_id, "credit_status": c["credit_status"], "payment_terms": c["payment_terms"],
            "active": bool(c["active"])}


def get_outstanding_balance(conn, customer_id):
    c = _customer(conn, customer_id)
    return {"customer_id": customer_id, "outstanding_rs": _rs(c["outstanding_paise"]),
            "credit_limit_rs": _rs(c["credit_limit_paise"]),
            "headroom_rs": _rs(c["credit_limit_paise"] - c["outstanding_paise"]), "payment_terms": c["payment_terms"]}


def list_customers_by_city(conn, city):
    return [dict(r) for r in conn.execute("SELECT id, name, tier, active FROM customers WHERE lower(city) = lower(?)", (city,))]


def get_customer_price_list(conn, customer_id):
    return [{"sku": r[0], "case_price_rs": _rs(r[1])} for r in
            conn.execute("SELECT sku, case_price_paise FROM customer_prices WHERE customer_id = ?", (customer_id,))]


# ---------- catalog
def search_products(conn, query):
    found = []
    for r in conn.execute("SELECT p.*, group_concat(a.alias, ' | ') AS aliases FROM products p "
                          "LEFT JOIN product_aliases a ON a.sku = p.sku GROUP BY p.sku"):
        score = _score(query, f"{r['sku']} {r['name']} {r['brand']} {r['type']} {r['variant']} {r['pack_size']} | {r['aliases']}")
        if score:
            found.append((score, {**_brief(r), "match_score": score}))
    return [p for _, p in sorted(found, key=lambda x: -x[0])][:8]


def get_sku_details(conn, sku):
    p = dict(_product(conn, sku))
    p["gst_rate_pct"], p["mrp_rs"] = p.pop("gst_rate_bp") / 100, _rs(p.pop("mrp_paise"))
    return p


def list_products_by_type(conn, product_type):
    return [_brief(r) for r in conn.execute("SELECT * FROM products WHERE lower(type) = lower(?) ORDER BY sku", (product_type,))]


def list_brands(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT brand FROM products ORDER BY brand")]


def get_product_aliases(conn, sku):
    _product(conn, sku)
    return [dict(r) for r in conn.execute("SELECT alias, script FROM product_aliases WHERE sku = ?", (sku,))]


def get_gst_rate(conn, sku):
    return {"sku": sku, "gst_rate_pct": _product(conn, sku)["gst_rate_bp"] / 100}


def get_mrp(conn, sku):
    return {"sku": sku, "mrp_per_piece_rs": _rs(_product(conn, sku)["mrp_paise"])}


# ---------- units
def get_units(conn, sku):
    _product(conn, sku)
    units = {r["unit_code"]: {"pieces_per_unit": r["pieces_per_unit"]} for r in
             conn.execute("SELECT * FROM product_units WHERE sku = ?", (sku,))}
    for r in conn.execute("SELECT * FROM unit_aliases"):
        if r["unit_code"] in units:
            units[r["unit_code"]].setdefault("aliases", []).append(r["alias"])
    return units


def convert_to_cases(conn, sku, quantity, unit):
    cases, rounded = to_cases(conn, sku, quantity, unit)
    return {"sku": sku, "cases": cases, "rounded_up": rounded}


def list_unit_aliases(conn):
    out = {}
    for r in conn.execute("SELECT unit_code, alias FROM unit_aliases"):
        out.setdefault(r[0], []).append(r[1])
    return out


# ---------- stock
def check_stock(conn, sku):
    _product(conn, sku)
    avail = conn.execute("SELECT COALESCE(SUM(on_hand_cases - reserved_cases), 0) FROM inventory WHERE sku = ?", (sku,)).fetchone()[0]
    return {"sku": sku, "available_cases": avail}


def get_warehouse_stock(conn, sku):
    _product(conn, sku)
    return [dict(r) for r in conn.execute(
        "SELECT warehouse_id, on_hand_cases, reserved_cases, on_hand_cases - reserved_cases AS available_cases "
        "FROM inventory WHERE sku = ?", (sku,))]


def get_restock_eta(conn, sku):
    _product(conn, sku)
    return [dict(r) for r in conn.execute("SELECT warehouse_id, expected_date, cases FROM restocks WHERE sku = ? "
                                          "ORDER BY expected_date", (sku,))]


def find_substitutes(conn, sku):
    _product(conn, sku)
    return [_brief(_product(conn, r[0])) for r in conn.execute("SELECT substitute_sku FROM substitutes WHERE sku = ?", (sku,))]


def list_low_stock(conn, max_cases=10):
    return [{"sku": r[0], "available_cases": r[1]} for r in conn.execute(
        "SELECT sku, SUM(on_hand_cases - reserved_cases) AS a FROM inventory GROUP BY sku HAVING a <= ? ORDER BY a",
        (max_cases,))]


# ---------- pricing
def get_standard_price(conn, sku):
    return {"sku": sku, "case_price_rs": _rs(conn.execute("SELECT case_price_paise FROM prices WHERE sku = ?",
                                                          (_product(conn, sku)["sku"],)).fetchone()[0])}


def get_bulk_price(conn, sku):
    _product(conn, sku)
    return [{"min_cases": r[0], "case_price_rs": _rs(r[1])} for r in
            conn.execute("SELECT min_cases, case_price_paise FROM bulk_prices WHERE sku = ? ORDER BY min_cases", (sku,))]


def get_customer_price(conn, customer_id, sku):
    _customer(conn, customer_id), _product(conn, sku)
    r = conn.execute("SELECT case_price_paise FROM customer_prices WHERE customer_id = ? AND sku = ?",
                     (customer_id, sku)).fetchone()
    return {"customer_id": customer_id, "sku": sku, "case_price_rs": _rs(r[0]) if r else None}


def get_discount_eligibility(conn, customer_id, cases):
    c = _customer(conn, customer_id)
    rule = conn.execute("SELECT * FROM discount_rules WHERE tier = ?", (c["tier"],)).fetchone()
    eligible = bool(c["active"]) and c["credit_status"] != "hold" and rule["discount_bp"] > 0 and cases >= rule["min_cases"]
    return {"customer_id": customer_id, "tier": c["tier"], "discount_pct": rule["discount_bp"] / 100 if eligible else 0,
            "min_cases": rule["min_cases"], "eligible": eligible,
            "note": "Not applied to customer-specific prices."}


def list_active_schemes(conn):
    d = conn.execute("SELECT value FROM policies WHERE key = 'business.date'").fetchone()[0]
    return [dict(r) for r in conn.execute("SELECT * FROM schemes WHERE valid_from <= ? AND valid_to >= ?", (d, d))]


def get_scheme_for_sku(conn, sku):
    _product(conn, sku)
    return [dict(r) for r in conn.execute("SELECT * FROM schemes WHERE sku = ?", (sku,))]


def _quote_json(q):
    return {"allowed": q.allowed, "flags": q.flags, "lines": [asdict(line) for line in q.lines],
            "subtotal_rs": _rs(q.subtotal_paise), "gst_rs": _rs(q.gst_paise), "total_rs": _rs(q.total_paise)}


def preview_quote(conn, customer_id, lines):
    return _quote_json(compute_quote(conn, customer_id, [(line["sku"], line["cases"]) for line in lines]))


# ---------- orders
def _order(conn, order_id):
    o = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if o is None:
        raise ValueError(f"unknown order {order_id}")
    lines = [{"sku": r[0], "cases": r[1], "case_price_rs": _rs(r[2])} for r in conn.execute(
        "SELECT sku, cases, case_price_paise FROM order_lines WHERE order_id = ? ORDER BY line_no", (order_id,))]
    return {"order_id": o["id"], "customer_id": o["customer_id"], "date": o["created_at"], "status": o["status"],
            "total_rs": _rs(o["total_paise"]), "lines": lines}


def get_order_history(conn, customer_id, limit=3):
    _customer(conn, customer_id)
    return [_order(conn, r[0]) for r in conn.execute(
        "SELECT id FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?", (customer_id, limit))]


def get_last_order(conn, customer_id):
    orders = get_order_history(conn, customer_id, 1)
    return orders[0] if orders else None


def get_order_details(conn, order_id):
    return _order(conn, order_id)


def get_order_status(conn, order_id):
    o = _order(conn, order_id)
    return {"order_id": order_id, "status": o["status"], "date": o["date"]}


def get_usual_products(conn, customer_id):
    _customer(conn, customer_id)
    return [{"sku": r[0], "times_ordered": r[1], "last_ordered": r[2]} for r in conn.execute(
        "SELECT ol.sku, COUNT(*), MAX(o.created_at) FROM order_lines ol JOIN orders o ON o.id = ol.order_id "
        "WHERE o.customer_id = ? GROUP BY ol.sku ORDER BY 2 DESC, 3 DESC", (customer_id,))]


# ---------- quotes (draft-only writes)
def _save_lines(conn, qid, q):
    conn.execute("DELETE FROM quote_lines WHERE quote_id = ?", (qid,))
    for n, line in enumerate(q.lines, 1):
        conn.execute("INSERT INTO quote_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (qid, n, line.sku, line.cases, line.free_cases, line.scheme_id, line.price_source,
                      line.case_price_paise, line.discount_bp, line.line_total_paise, line.gst_paise,
                      line.available_cases, line.shortage_cases, line.note))
    conn.execute("UPDATE quotes SET flags = ? WHERE id = ?", (json.dumps(q.flags), qid))


def create_draft_quote(conn, customer_id, lines, notes=""):
    q = compute_quote(conn, customer_id, [(line["sku"], line["cases"]) for line in lines])
    if not q.allowed:
        return {"error": "quote not allowed", "flags": q.flags}
    n = conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0] + 1
    qid = f"Q-{n:04d}"
    conn.execute("INSERT INTO quotes (id, customer_id, status, created_at, notes) VALUES (?,?,?,?,?)",
                 (qid, customer_id, "draft", datetime.now().isoformat(timespec="seconds"), notes))
    _save_lines(conn, qid, q)
    conn.commit()
    return {"quote_id": qid, **_quote_json(q)}


def get_draft_quote(conn, quote_id):
    qt = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
    if qt is None:
        raise ValueError(f"unknown quote {quote_id}")
    lines = [dict(r) for r in conn.execute("SELECT * FROM quote_lines WHERE quote_id = ? ORDER BY line_no", (quote_id,))]
    return {**dict(qt), "lines": lines}


def list_draft_quotes(conn, customer_id=None):
    sql, args = "SELECT id, customer_id, created_at FROM quotes", ()
    if customer_id:
        sql, args = sql + " WHERE customer_id = ?", (customer_id,)
    return [dict(r) for r in conn.execute(sql, args)]


def update_draft_quote(conn, quote_id, lines):
    qt = conn.execute("SELECT customer_id FROM quotes WHERE id = ?", (quote_id,)).fetchone()
    if qt is None:
        raise ValueError(f"unknown quote {quote_id}")
    q = compute_quote(conn, qt[0], [(line["sku"], line["cases"]) for line in lines])
    _save_lines(conn, quote_id, q)
    conn.commit()
    return {"quote_id": quote_id, **_quote_json(q)}


def discard_draft_quote(conn, quote_id):
    conn.execute("DELETE FROM quote_lines WHERE quote_id = ?", (quote_id,))
    deleted = conn.execute("DELETE FROM quotes WHERE id = ?", (quote_id,)).rowcount
    conn.commit()
    return {"quote_id": quote_id, "discarded": bool(deleted)}


# ---------- policy
def get_policies(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT * FROM policies")}


def get_policy(conn, key):
    r = conn.execute("SELECT value FROM policies WHERE key = ?", (key,)).fetchone()
    return {"key": key, "value": r[0] if r else None,
            "known_keys": None if r else [k[0] for k in conn.execute("SELECT key FROM policies")]}


T = Tool
REGISTRY: list[Tool] = [
    T("find_customer", "customers", "Find retailers by name or alias (English, Telugu script, Roman Telugu). Returns candidates.", params(["query"], query=S), find_customer),
    T("get_customer_profile", "customers", "Full profile of one customer: city, tier, terms, credit, aliases.", params(["customer_id"], customer_id=S), get_customer_profile),
    T("get_credit_status", "customers", "Credit status (ok / watch / hold), payment terms and whether the customer is active.", params(["customer_id"], customer_id=S), get_credit_status),
    T("get_outstanding_balance", "customers", "Outstanding balance, credit limit and remaining headroom for a customer.", params(["customer_id"], customer_id=S), get_outstanding_balance),
    T("list_customers_by_city", "customers", "List customers in a city.", params(["city"], city=S), list_customers_by_city),
    T("get_customer_price_list", "customers", "All negotiated customer-specific case prices for a customer.", params(["customer_id"], customer_id=S), get_customer_price_list),
    T("search_products", "catalog", "Search the catalogue by name, brand, type, pack size or alias. Returns candidate SKUs.", params(["query"], query=S), search_products),
    T("get_sku_details", "catalog", "Details of one SKU: brand, type, variant, pack, units per case, GST, MRP.", params(["sku"], sku=S), get_sku_details),
    T("list_products_by_type", "catalog", "All SKUs of a product type, e.g. 'sunflower oil', 'toor dal'.", params(["product_type"], product_type=S), list_products_by_type),
    T("list_brands", "catalog", "All brands the distributor stocks.", params(), list_brands),
    T("get_product_aliases", "catalog", "Known aliases of a SKU in English, Telugu script and Roman Telugu.", params(["sku"], sku=S), get_product_aliases),
    T("get_gst_rate", "catalog", "GST rate of a SKU.", params(["sku"], sku=S), get_gst_rate),
    T("get_mrp", "catalog", "Printed MRP per piece of a SKU.", params(["sku"], sku=S), get_mrp),
    T("get_units", "units", "Units a SKU can be ordered in and pieces per unit, with unit aliases (petti, bastha, dabba...).", params(["sku"], sku=S), get_units),
    T("convert_to_cases", "units", "Convert a quantity in any unit (case, piece, dozen, kg, litre, bag, tin) to whole cases, rounding up.", params(["sku", "quantity", "unit"], sku=S, quantity={"type": "number"}, unit=S), convert_to_cases),
    T("list_unit_aliases", "units", "All unit codes and their aliases in English, Telugu and Roman Telugu.", params(), list_unit_aliases),
    T("check_stock", "stock", "Total available cases of a SKU across warehouses.", params(["sku"], sku=S), check_stock),
    T("get_warehouse_stock", "stock", "Per-warehouse on-hand, reserved and available cases of a SKU.", params(["sku"], sku=S), get_warehouse_stock),
    T("get_restock_eta", "stock", "Expected restocks of a SKU: date and cases.", params(["sku"], sku=S), get_restock_eta),
    T("find_substitutes", "stock", "Approved substitute SKUs for a SKU.", params(["sku"], sku=S), find_substitutes),
    T("list_low_stock", "stock", "SKUs with available cases at or below a threshold.", params(max_cases={"type": "integer"}), list_low_stock),
    T("get_standard_price", "pricing", "Standard (list) case price of a SKU.", params(["sku"], sku=S), get_standard_price),
    T("get_bulk_price", "pricing", "Bulk case-price tiers of a SKU by minimum cases.", params(["sku"], sku=S), get_bulk_price),
    T("get_customer_price", "pricing", "Negotiated case price of a SKU for one customer, if any.", params(["customer_id", "sku"], customer_id=S, sku=S), get_customer_price),
    T("get_discount_eligibility", "pricing", "Whether a customer's tier discount applies for a line of N cases.", params(["customer_id", "cases"], customer_id=S, cases=I), get_discount_eligibility),
    T("list_active_schemes", "pricing", "Trade schemes valid on the business date (buy N get M free).", params(), list_active_schemes),
    T("get_scheme_for_sku", "pricing", "All schemes (active or expired) for a SKU.", params(["sku"], sku=S), get_scheme_for_sku),
    T("preview_quote", "pricing", "Price lines for a customer without saving: prices, discounts, schemes, GST, stock and flags.", params(["customer_id", "lines"], customer_id=S, lines=LINES), preview_quote),
    T("get_order_history", "orders", "A customer's most recent orders with lines.", params(["customer_id"], customer_id=S, limit={"type": "integer"}), get_order_history),
    T("get_last_order", "orders", "A customer's most recent order with lines.", params(["customer_id"], customer_id=S), get_last_order),
    T("get_order_details", "orders", "Lines, prices and status of one order.", params(["order_id"], order_id=S), get_order_details),
    T("get_order_status", "orders", "Status of one order (confirmed, dispatched, delivered).", params(["order_id"], order_id=S), get_order_status),
    T("get_usual_products", "orders", "SKUs a customer orders most often, with last order date.", params(["customer_id"], customer_id=S), get_usual_products),
    T("create_draft_quote", "quotes", "Save a draft quote for a customer. Lines are whole cases. Draft only; never confirms an order.", params(["customer_id", "lines"], customer_id=S, lines=LINES, notes=S), create_draft_quote, writes=True),
    T("get_draft_quote", "quotes", "Read one draft quote with its lines.", params(["quote_id"], quote_id=S), get_draft_quote),
    T("list_draft_quotes", "quotes", "List draft quotes, optionally for one customer.", params(customer_id=S), list_draft_quotes),
    T("update_draft_quote", "quotes", "Replace the lines of an existing draft quote.", params(["quote_id", "lines"], quote_id=S, lines=LINES), update_draft_quote, writes=True),
    T("discard_draft_quote", "quotes", "Discard a draft quote created by mistake.", params(["quote_id"], quote_id=S), discard_draft_quote, writes=True),
    T("get_policies", "policy", "All business policies: pricing, discounts, schemes, credit, units, defaults, quoting.", params(), get_policies),
    T("get_policy", "policy", "One business policy by key.", params(["key"], key=S), get_policy),
]
BY_NAME = {t.name: t for t in REGISTRY}

# The 8 tools of the first sample run (baseline B0).
CORE = ["find_customer", "search_products", "get_order_history", "get_units", "check_stock", "get_policies",
        "preview_quote", "create_draft_quote"]


def chat_tools(names: list[str] | None = None) -> list[dict]:
    """Chat Completions format (arm A, and B0 with CORE)."""
    return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in REGISTRY if names is None or t.name in names]


def responses_tools() -> list[dict]:
    """Responses API format for Muse hosted tool search (arm B): every function deferred inside a namespace."""
    out = []
    for ns, desc in NAMESPACES.items():
        fns = [{"type": "function", "name": t.name, "description": t.description, "parameters": t.parameters,
                "defer_loading": True} for t in REGISTRY if t.namespace == ns]
        out.append({"type": "namespace", "name": ns, "description": desc, "tools": fns})
    return out + [{"type": "tool_search"}]


def call(conn: sqlite3.Connection, name: str, args: dict):
    """Run a tool; errors come back as data, as a real tool server would return them."""
    tool = BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name}"}
    try:
        return tool.fn(conn, **args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
