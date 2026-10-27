"""Sample baseline run: a minimal Muse tool-calling agent on a few benchmark tasks.

Throwaway preview of the Day 2-3 baseline: 8 simple tools over the SQLite business, a bounded
tool loop, and a grader that checks the saved draft quote against the task's answer key.
Each task runs on a freshly reset DB.

Usage:
  uv run python scripts/smoke/sample_run.py                      # D01 D09 D16 D19 D28
  uv run python scripts/smoke/sample_run.py --tasks D02 H05 --model muse-spark-1.3
"""

import argparse
import json
import re
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from order_agent import db  # noqa: E402
from order_agent.llm import MuseClient  # noqa: E402
from order_agent.pricing import compute_quote  # noqa: E402

TASKS = ROOT / "datasets" / "tasks" / "benchmark_v1.jsonl"
DEFAULT_TASKS = ["D01", "D09", "D16", "D19", "D28"]
MAX_TURNS = 10

SYSTEM = (
    "You are the order-desk assistant of a wholesale FMCG distributor in Andhra Pradesh. Requests come from "
    "the operator in English, Telugu script, Roman Telugu or a mix. Use the tools to look up customers, "
    "products, units, stock, history and policies; never invent them. Follow the business policies "
    "(get_policies). When the request is clear, create exactly one draft quote with create_draft_quote, then "
    "reply with a short summary. If the customer or product is ambiguous, or a quote is not allowed, do not "
    "create a quote: explain why or ask the operator a clarifying question. Never confirm orders."
)


def fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props, "required": required}}}


LINES = {"type": "array", "items": {"type": "object", "properties": {
    "sku": {"type": "string"}, "cases": {"type": "integer", "minimum": 1}}, "required": ["sku", "cases"]}}

TOOLS = [
    fn("find_customer", "Find customers by name or alias (English, Telugu script, Roman Telugu).",
       {"query": {"type": "string"}}, ["query"]),
    fn("search_products", "Search the catalogue by name, brand, type, pack size or alias. Returns candidate SKUs.",
       {"query": {"type": "string"}}, ["query"]),
    fn("get_order_history", "A customer's most recent orders with their lines.",
       {"customer_id": {"type": "string"}, "limit": {"type": "integer", "default": 3}}, ["customer_id"]),
    fn("get_units", "Units a SKU can be ordered in (case, piece, dozen, kg, litre, bag, tin) and pieces per unit, "
       "plus unit aliases such as petti, bastha, dabba.", {"sku": {"type": "string"}}, ["sku"]),
    fn("check_stock", "Available cases of a SKU across warehouses, restocks and substitutes.",
       {"sku": {"type": "string"}}, ["sku"]),
    fn("get_policies", "The distributor's pricing, discount, scheme, credit, unit and quoting policies.", {}, []),
    fn("preview_quote", "Price lines for a customer without saving: prices, discounts, schemes, GST, stock, flags.",
       {"customer_id": {"type": "string"}, "lines": LINES}, ["customer_id", "lines"]),
    fn("create_draft_quote", "Save a draft quote (draft only; never confirms an order). Lines are in whole cases.",
       {"customer_id": {"type": "string"}, "lines": LINES, "notes": {"type": "string"}}, ["customer_id", "lines"]),
]


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,.;:!?()/-]+", text.lower()) if t]


def tool_find_customer(conn, query):
    rows = {}
    for r in conn.execute("SELECT c.*, group_concat(a.alias, ' | ') AS aliases FROM customers c "
                          "LEFT JOIN customer_aliases a ON a.customer_id = c.id GROUP BY c.id"):
        hay = f"{r['name']} {r['aliases']}".lower()
        score = sum(t in hay for t in tokens(query))
        if score:
            rows[r["id"]] = (score, {k: r[k] for k in ("id", "name", "city", "tier", "active", "credit_status")})
    return [v for _, v in sorted(rows.values(), key=lambda x: -x[0])][:6]


def tool_search_products(conn, query):
    found = []
    for r in conn.execute("SELECT p.*, group_concat(a.alias, ' | ') AS aliases FROM products p "
                          "LEFT JOIN product_aliases a ON a.sku = p.sku GROUP BY p.sku"):
        hay = f"{r['sku']} {r['name']} {r['brand']} {r['type']} {r['variant']} {r['pack_size']} {r['aliases']}".lower()
        score = sum(t in hay for t in tokens(query))
        if score:
            found.append((score, {"sku": r["sku"], "name": r["name"], "pack_size": r["pack_size"],
                                  "units_per_case": r["units_per_case"]}))
    return [p for _, p in sorted(found, key=lambda x: -x[0])][:8]


def tool_get_order_history(conn, customer_id, limit=3):
    out = []
    for o in conn.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?", (customer_id, limit)):
        lines = [dict(sku=r["sku"], cases=r["cases"]) for r in
                 conn.execute("SELECT sku, cases FROM order_lines WHERE order_id = ? ORDER BY line_no", (o["id"],))]
        out.append({"order_id": o["id"], "date": o["created_at"], "status": o["status"], "lines": lines})
    return out


def tool_get_units(conn, sku):
    units = {r["unit_code"]: {"pieces_per_unit": r["pieces_per_unit"]} for r in
             conn.execute("SELECT * FROM product_units WHERE sku = ?", (sku,))}
    for r in conn.execute("SELECT * FROM unit_aliases"):
        if r["unit_code"] in units:
            units[r["unit_code"]].setdefault("aliases", []).append(r["alias"])
    return units or {"error": f"unknown sku {sku}"}


def tool_check_stock(conn, sku):
    avail = conn.execute("SELECT COALESCE(SUM(on_hand_cases - reserved_cases), 0) FROM inventory WHERE sku = ?", (sku,)).fetchone()[0]
    restocks = [dict(r) for r in conn.execute("SELECT expected_date, cases FROM restocks WHERE sku = ?", (sku,))]
    subs = [r[0] for r in conn.execute("SELECT substitute_sku FROM substitutes WHERE sku = ?", (sku,))]
    return {"sku": sku, "available_cases": avail, "restocks": restocks, "substitutes": subs}


def tool_get_policies(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT * FROM policies")}


def quote_dict(q):
    return {"allowed": q.allowed, "flags": q.flags, "lines": [asdict(line) for line in q.lines],
            "total_rs": q.total_paise / 100}


def tool_preview_quote(conn, customer_id, lines):
    return quote_dict(compute_quote(conn, customer_id, [(line["sku"], line["cases"]) for line in lines]))


def tool_create_draft_quote(conn, customer_id, lines, notes=""):
    q = compute_quote(conn, customer_id, [(line["sku"], line["cases"]) for line in lines])
    if not q.allowed:
        return {"error": "quote not allowed", "flags": q.flags}
    qid = f"Q-{conn.execute('SELECT COUNT(*) FROM quotes').fetchone()[0] + 1:04d}"
    conn.execute("INSERT INTO quotes (id, customer_id, status, created_at, flags, notes) VALUES (?,?,?,?,?,?)",
                 (qid, customer_id, "draft", datetime.now().isoformat(timespec="seconds"), json.dumps(q.flags), notes))
    for n, line in enumerate(q.lines, 1):
        conn.execute("INSERT INTO quote_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (qid, n, line.sku, line.cases, line.free_cases, line.scheme_id, line.price_source,
                      line.case_price_paise, line.discount_bp, line.line_total_paise, line.gst_paise,
                      line.available_cases, line.shortage_cases, line.note))
    conn.commit()
    return {"quote_id": qid, **quote_dict(q)}


IMPL = {name: globals()[f"tool_{name}"] for name in (t["function"]["name"] for t in TOOLS)}


def run_task(client, task):
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(db.reset(Path(tmp) / "business.db"))
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["request"]}]
        trace, cost, tokens_in, tokens_out, final = [], 0.0, 0, 0, ""
        for _ in range(MAX_TURNS):
            r = client.chat(messages, TOOLS, temperature=0)
            cost, tokens_in, tokens_out = cost + r.cost_usd, tokens_in + r.tokens_in, tokens_out + r.tokens_out
            messages.append(r.assistant_message())
            if not r.tool_calls:
                final = r.content or ""
                break
            for tc in r.tool_calls:
                try:
                    result = IMPL[tc.name](conn, **tc.parsed_args())
                except Exception as e:  # tool errors go back to the model, as a real server would
                    result = {"error": f"{type(e).__name__}: {e}"}
                trace.append({"tool": tc.name, "args": tc.parsed_args(), "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
        quotes = [dict(q) for q in conn.execute("SELECT * FROM quotes")]
        lines = [dict(sku=r["sku"], cases=r["cases"]) for r in conn.execute("SELECT sku, cases FROM quote_lines")]
        conn.close()
    verdict, why = grade(task["expected"], quotes, lines)
    return {"id": task["id"], "lang": task["lang"], "tags": task["tags"], "request": task["request"],
            "pass": verdict, "why": why, "final_reply": final, "quotes": quotes, "quote_lines": lines,
            "tool_calls": len(trace), "trace": trace, "cost_usd": round(cost, 5),
            "tokens_in": tokens_in, "tokens_out": tokens_out}


def grade(exp, quotes, lines):
    if exp["action"] != "quote":
        return (not quotes, "no quote, as expected" if not quotes else f"created {len(quotes)} quote(s); expected {exp['action']}")
    if len(quotes) != 1:
        return False, f"expected 1 quote, got {len(quotes)}"
    if quotes[0]["customer_id"] != exp["customer_id"]:
        return False, f"customer {quotes[0]['customer_id']} != {exp['customer_id']}"
    got = sorted((line["sku"], line["cases"]) for line in lines)
    want = sorted((line["sku"], line["cases"]) for line in exp["lines"])
    if got != want:
        return False, f"lines {got} != {want}"
    return True, "lines and customer match"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    ap.add_argument("--model", default="muse-spark-1.3")
    args = ap.parse_args()

    tasks = {t["id"]: t for t in map(json.loads, TASKS.read_text(encoding="utf-8").splitlines())}
    client = MuseClient(model=args.model)
    results = []
    for tid in args.tasks:
        res = run_task(client, tasks[tid])
        results.append(res)
        mark = "✅" if res["pass"] else "❌"
        print(f"{mark} {tid} [{res['lang']}] {res['request']}")
        print(f"   {res['why']} · {res['tool_calls']} tool calls · ${res['cost_usd']}")
        print(f"   tools: {' → '.join(s['tool'] for s in res['trace'])}")
        print(f"   reply: {res['final_reply'][:220]}\n")

    passed = sum(r["pass"] for r in results)
    total_cost = sum(r["cost_usd"] for r in results)
    print(f"Passed {passed}/{len(results)} · cost ${total_cost:.4f}")
    out = ROOT / "artifacts" / "sample_runs" / f"sample_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Trace saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
