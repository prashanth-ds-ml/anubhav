from collections import Counter

import pytest

from order_agent import db, tools


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    c = db.connect(db.reset(tmp_path_factory.mktemp("tools") / "business.db"))
    yield c
    c.close()


def test_registry_shape():
    assert len(tools.REGISTRY) == 40 and len(tools.BY_NAME) == 40
    per_ns = Counter(t.namespace for t in tools.REGISTRY)
    assert set(per_ns) == set(tools.NAMESPACES) and max(per_ns.values()) < 10  # Muse tool-search guidance
    assert {t.name for t in tools.REGISTRY if t.writes} == {"create_draft_quote", "update_draft_quote", "discard_draft_quote"}
    assert set(tools.CORE) <= set(tools.BY_NAME)


def test_export_formats():
    assert len(tools.chat_tools()) == 40 and len(tools.chat_tools(tools.CORE)) == 8
    rt = tools.responses_tools()
    assert rt[-1] == {"type": "tool_search"}
    assert all(f["defer_loading"] for ns in rt[:-1] for f in ns["tools"])


@pytest.mark.parametrize("query, expected", [
    ("Anjali mart", ["C-007"]),                 # must not also match "Vijaya Mart"
    ("Ravi Traders", ["C-001"]),
    ("రవి", ["C-001", "C-015"]),               # genuinely ambiguous
    ("Sai shop", ["C-011", "C-017"]),           # "shop" is filler
    ("SV stores", ["C-003"]),
])
def test_find_customer(conn, query, expected):
    assert sorted(c["id"] for c in tools.find_customer(conn, query)) == expected


@pytest.mark.parametrize("query, top", [
    ("noodles 70g", "KF-NOOD-70"),
    ("coffee podi 200g", "DP-COFFEE-200"),
    ("sona masoori 25kg", "KS-SONA-25"),
    ("Godavari Gold sunflower nune 1 litre", "GG-SUN-1L"),
])
def test_search_products_ranks_exact_pack_first(conn, query, top):
    assert tools.search_products(conn, query)[0]["sku"] == top


def test_hidden_slang_is_not_findable(conn):
    assert tools.search_products(conn, "జీజీ ఆయిల్") == []
    assert tools.find_customer(conn, "Venkanna") == []


def test_draft_quote_lifecycle(tmp_path):
    c = db.connect(db.reset(tmp_path / "b.db"))
    q = tools.call(c, "create_draft_quote", {"customer_id": "C-001", "lines": [{"sku": "GG-SUN-1L", "cases": 12}]})
    assert q["quote_id"] == "Q-0001" and q["flags"] == ["shortage"]
    u = tools.call(c, "update_draft_quote", {"quote_id": "Q-0001", "lines": [{"sku": "GG-SUN-1L", "cases": 5}]})
    assert u["flags"] == [] and u["lines"][0]["cases"] == 5
    assert tools.call(c, "discard_draft_quote", {"quote_id": "Q-0001"})["discarded"]
    assert c.execute("SELECT COUNT(*) FROM quotes").fetchone()[0] == 0
    assert "error" in tools.call(c, "create_draft_quote", {"customer_id": "C-010", "lines": [{"sku": "KF-SUGAR-1", "cases": 1}]})
    assert "error" in tools.call(c, "no_such_tool", {})
    c.close()


@pytest.mark.parametrize("tool", tools.REGISTRY, ids=lambda t: t.name)
def test_every_read_tool_runs(conn, tool):
    if tool.writes:
        return
    sample = {"query": "sugar", "customer_id": "C-001", "sku": "GG-SUN-1L", "city": "Guntur", "product_type": "ghee",
              "quantity": 2, "unit": "case", "cases": 10, "order_id": "O-1006", "quote_id": "Q-9999",
              "lines": [{"sku": "GG-SUN-1L", "cases": 2}], "key": "credit.hold"}
    required = tool.parameters.get("required", [])
    result = tools.call(conn, tool.name, {k: sample[k] for k in required})
    if tool.name != "get_draft_quote":  # no quote exists in a fresh DB
        assert not (isinstance(result, dict) and "error" in result), result
