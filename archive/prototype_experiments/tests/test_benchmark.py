"""Integrity checks for the benchmark tasks, so a baseline failure means the agent failed, not the task."""

import json
from collections import Counter
from pathlib import Path

import pytest

from order_agent import db
from order_agent.db.seed import DATA, read_csv
from order_agent.pricing import compute_quote

TASKS = Path(__file__).resolve().parents[1] / "datasets" / "tasks" / "benchmark_v1.jsonl"


def load_tasks():
    return [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    c = db.connect(db.reset(tmp_path_factory.mktemp("bench") / "business.db"))
    yield c
    c.close()


def test_shape_matches_prd():
    tasks = load_tasks()
    assert len(tasks) == 48 and len({t["id"] for t in tasks}) == 48
    assert Counter(t["split"] for t in tasks) == {"dev": 32, "heldout": 16}
    assert Counter(t["lang"] for t in tasks) == {"en": 8, "te": 12, "roman": 16, "mixed": 12}


@pytest.mark.parametrize("task", load_tasks(), ids=lambda t: t["id"])
def test_expected_answer_is_consistent(conn, task):
    exp = task["expected"]
    if exp["action"] == "quote":
        q = compute_quote(conn, exp["customer_id"], [(line["sku"], line["cases"]) for line in exp["lines"]])
        assert q.allowed
        assert q.flags == exp["flags"] and q.total_paise == exp["total_paise"]
        cats = {conn.execute("SELECT category FROM products WHERE sku = ?", (line["sku"],)).fetchone()[0]
                for line in exp["lines"]}
        assert not cats & set(exp["forbidden_categories"])
        assert not {line["sku"] for line in exp["lines"]} & set(exp["forbidden_skus"])
    elif exp["action"] == "no_quote":
        assert not compute_quote(conn, exp["customer_id"], []).allowed
    else:
        assert exp["clarify"] in ("customer", "product")


def test_hidden_knowledge_is_not_in_db(conn):
    """Shop slang must be learnable only from experience: it is in hidden/, never in the lookup tables."""
    slang = {r["term"].lower() for r in read_csv("hidden/shop_slang.csv", DATA)}
    aliases = {r[0].lower() for r in conn.execute(
        "SELECT alias FROM product_aliases UNION SELECT alias FROM customer_aliases UNION SELECT alias FROM unit_aliases")}
    assert not slang & aliases
    for task in load_tasks():
        for term in task["hidden_knowledge"]:
            assert term.lower() in slang, (task["id"], term)
            assert term.lower() in task["request"].lower(), (task["id"], term)


def test_customer_ambiguity_is_real(conn):
    """'Ravi', 'Sai' and 'Lakshmi' each match more than one active customer."""
    for word in ("Ravi", "Sai", "Lakshmi"):
        n = conn.execute("SELECT COUNT(*) FROM customers WHERE active = 1 AND name LIKE ?", (f"%{word}%",)).fetchone()[0]
        assert n > 1, word


def test_product_ambiguity_is_real(conn):
    """Clarify-product tasks: several SKUs of the type, and no order history to default from."""
    cases = {"D11": ("C-009", "sunflower oil"), "H11": ("C-004", "toor dal")}
    for tid, (cid, ptype) in cases.items():
        assert conn.execute("SELECT COUNT(*) FROM products WHERE type = ?", (ptype,)).fetchone()[0] > 1, tid
        history = conn.execute(
            "SELECT COUNT(*) FROM order_lines ol JOIN orders o ON o.id = ol.order_id JOIN products p ON p.sku = ol.sku"
            " WHERE o.customer_id = ? AND p.type = ?", (cid, ptype)).fetchone()[0]
        assert history == 0, tid


def test_history_defaults_point_at_last_bought_sku(conn):
    """Tasks tagged history_default expect the SKU from the customer's most recent order of that type."""
    for task in load_tasks():
        if "history_default" not in task["tags"]:
            continue
        exp = task["expected"]
        for line in exp["lines"]:
            ptype = conn.execute("SELECT type FROM products WHERE sku = ?", (line["sku"],)).fetchone()[0]
            last = conn.execute(
                "SELECT ol.sku FROM order_lines ol JOIN orders o ON o.id = ol.order_id JOIN products p ON p.sku = ol.sku"
                " WHERE o.customer_id = ? AND p.type = ? ORDER BY o.created_at DESC LIMIT 1",
                (exp["customer_id"], ptype)).fetchone()
            if last is not None:
                assert last[0] == line["sku"], (task["id"], line["sku"])


def test_history_repeat_matches_last_order(conn):
    for task in load_tasks():
        if "history_repeat" not in task["tags"]:
            continue
        exp = task["expected"]
        last = conn.execute("SELECT id FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1",
                            (exp["customer_id"],)).fetchone()[0]
        lines = [{"sku": r[0], "cases": r[1]} for r in
                 conn.execute("SELECT sku, cases FROM order_lines WHERE order_id = ? ORDER BY line_no", (last,))]
        assert lines == exp["lines"], task["id"]
