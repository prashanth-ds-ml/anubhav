import json

import pytest

from order_agent import db
from order_agent.llm import MockClient, cost_usd, mock_final, mock_tool_call


@pytest.fixture
def conn(tmp_path):
    path = db.reset(tmp_path / "business.db")
    c = db.connect(path)
    yield c
    c.close()


def test_seed_counts(conn):
    count = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    assert count("products") == 40
    assert count("customers") == 15
    assert count("prices") == 40
    assert count("inventory") == 80


def test_golden_path_fixture(conn):
    ravi = conn.execute("SELECT * FROM customers WHERE name = 'Ravi Traders'").fetchone()
    assert ravi["tier"] == "gold" and ravi["credit_status"] == "ok" and ravi["active"] == 1
    assert "రవి ట్రేడర్స్" in json.loads(ravi["aliases"])

    available = conn.execute(
        "SELECT SUM(on_hand_cases - reserved_cases) FROM inventory WHERE sku = 'GG-SUN-1L'"
    ).fetchone()[0]
    assert available == 8

    price = conn.execute("SELECT case_price_paise FROM prices WHERE sku = 'GG-SUN-1L'").fetchone()[0]
    assert price == 174000
    rule = conn.execute("SELECT * FROM discount_rules WHERE tier = 'gold'").fetchone()
    assert (rule["discount_bp"], rule["min_cases"]) == (500, 10)


def test_ambiguous_products_exist(conn):
    # "sunflower oil" alone must be ambiguous (brands and sizes) -> clarification scenarios
    rows = conn.execute("SELECT sku FROM products WHERE name LIKE '%Sunflower Oil%'").fetchall()
    assert len(rows) == 3


def test_reset_is_deterministic(tmp_path):
    dump = []
    for i in range(2):
        c = db.connect(db.reset(tmp_path / f"b{i}.db"))
        dump.append(list(c.iterdump()))
        c.close()
    assert dump[0] == dump[1]


def test_quotes_are_draft_only(conn):
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO quotes (id, customer_id, status, created_at) VALUES ('Q1', 'C-001', 'confirmed', 'now')"
        )


def test_mock_client_scripted_flow():
    client = MockClient([mock_tool_call("find_customer", {"name": "Ravi Traders"}), mock_final("done")])
    r1 = client.chat([{"role": "user", "content": "hi"}], tools=[])
    assert r1.tool_calls[0].parsed_args() == {"name": "Ravi Traders"}
    assert r1.assistant_message()["tool_calls"][0]["function"]["name"] == "find_customer"
    assert client.chat([]).content == "done"
    with pytest.raises(RuntimeError):
        client.chat([])


def test_cost():
    assert cost_usd("muse-spark-1.3", 1_000_000, 1_000_000) == pytest.approx(5.50)
