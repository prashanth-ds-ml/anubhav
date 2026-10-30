"""The read-only query sandbox (D-040): one SELECT over the company's own records, nothing else."""

import pytest

from anubhav.data import generate
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import QueryError, Sandbox


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture(scope="module")
def sb(world, tmp_path_factory):
    return Sandbox(CompanyData(world, "T01", tmp_path_factory.mktemp("rt")))


def test_a_select_answers_from_the_company_records(sb, world, tmp_path):
    C = CompanyData(world, "T01", tmp_path)
    r = sb.run("select count(*) as n from orders")
    assert r["columns"] == ["n"] and r["rows"] == [[len(C.orders)]] and r["tables_read"] == ["orders"]
    r = sb.run("select o.site_id, count(*) n from orders o join sites s on s.site_id = o.site_id group by 1 order by 2 desc limit 3")
    assert r["row_count"] == 3 and set(r["tables_read"]) == {"orders", "sites"}


def test_the_schema_comes_from_the_data(sb):
    s = sb.schema()
    assert "orders(" in s and "delivery_date TEXT" in s and "payload_kg INTEGER" in s
    assert "planner_messages" in s and "text TEXT [free text]" in s


@pytest.mark.parametrize("sql", [
    "insert into orders(order_id) values ('X')", "update vehicles set payload_kg = 1", "delete from orders",
    "drop table orders", "create table x(a)", "create temp table x as select 1", "attach database 'evil.db' as e",
    "pragma query_only = off", "select * from sqlite_master", "select load_extension('x')",
    "select 1; delete from orders", "with recursive c(x) as (select 1 union all select x + 1 from c) insert into orders(order_id) select x from c",
])
def test_anything_but_a_read_is_refused(sb, sql):
    with pytest.raises(QueryError) as e:
        sb.run(sql)
    assert e.value.code in ("FORBIDDEN", "BAD_ARGS")
    assert sb.run("select count(*) from orders")["rows"][0][0] > 0       # nothing changed


def test_a_query_that_never_ends_is_stopped(sb):
    with pytest.raises(QueryError) as e:
        sb.run("with recursive c(x) as (select 1 union all select x + 1 from c) select count(*) from c", timeout_s=0.3)
    assert e.value.code == "LIMIT"


def test_rows_and_length_are_capped(sb):
    r = sb.run("select * from trip_events", max_rows=50)
    assert r["row_count"] == 50 and r["truncated"]
    with pytest.raises(QueryError):
        sb.run("select 1 " + " " * 5000 + "-- long")


def test_another_company_is_not_reachable(world, tmp_path):
    t1 = Sandbox(CompanyData(world, "T01", tmp_path / "a"))
    t2_orders = {o for (o,) in Sandbox(CompanyData(world, "T02", tmp_path / "b")).run("select order_id from orders", max_rows=5000)["rows"]}
    t1_orders = {o for (o,) in t1.run("select order_id from orders", max_rows=5000)["rows"]}
    assert not (t1_orders & t2_orders)
    assert "drafts" not in t1.tables and "audit" not in t1.tables


def test_reading_peoples_free_text_marks_the_result_untrusted(sb):
    assert "untrusted_text" in sb.run("select text from planner_messages limit 2")
    assert "untrusted_text" not in sb.run("select count(*) from planner_messages")


# ---------- C2: the tools, offered only when analysis is switched on
def test_analysis_tools_are_off_unless_switched_on(world, tmp_path):
    from anubhav.runtime.broker import Broker, Session
    C = CompanyData(world, "T01", tmp_path)
    off, on = Broker(C, Session("T01")), Broker(C, Session("T01"), analysis=True)
    assert "run_query" not in {t.name for t in off.list_tools()} and off.call("run_query", {"sql": "select 1", "purpose": "x"})["error"]["code"] == "NOT_FOUND"
    assert {"run_query", "describe_tables"} <= {t["function"]["name"] for t in on.openai_tools()}
    assert "orders(" in on.call("describe_tables", {})["result"]["schema"]
    r = on.call("run_query", {"sql": "select count(*) n from vehicles", "purpose": "how many vehicles"})
    assert r["ok"] and r["result"]["rows"] == [[len(C.vehicles)]]


def test_query_errors_reach_the_model_as_typed_errors(world, tmp_path):
    from anubhav.runtime.broker import Broker, Session
    b = Broker(CompanyData(world, "T01", tmp_path), Session("T01", "viewer"), analysis=True)
    assert b.call("run_query", {"sql": "select nope from orders", "purpose": "x"})["error"]["code"] == "BAD_ARGS"
    assert b.call("run_query", {"sql": "delete from orders", "purpose": "x"})["error"]["code"] == "FORBIDDEN"
    assert b.call("run_query", {"sql": "select count(*) from orders", "purpose": "viewers may read"})["ok"]
