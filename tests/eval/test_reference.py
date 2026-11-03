"""Benchmark reference answers come from the same tables the agent reads (the sandbox), so one SQL works for every
company whatever its raw file layout. No model is called."""

import json

import pytest

from anubhav.data import generate
from anubhav.data.config import ROOT
from anubhav.eval.reference import reference_sandbox, run_reference_sql
from anubhav.runtime.query import QueryError

TEMPLATE = ROOT / "benchmark" / "questions_template.jsonl"
SEED7919 = ROOT / "data" / "worlds" / "full_seed7919"
RETURNED = ("select coalesce(sum(t.returned_cases),0) from trip_outcomes t join sites s using(site_id) "
            "where s.town = (select town from sites group by town order by count(*) desc, town limit 1) "
            "and substr(t.arrived_at,6,2)='09'")
OPEN = "select count(*) from orders where status='open'"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


def test_the_two_companies_have_the_same_tables_and_columns(world):
    a, b = reference_sandbox(world, "T01"), reference_sandbox(world, "T02")
    assert a is reference_sandbox(world, "T01")            # one sandbox per (world, company)
    for name in ("orders", "order_items", "sites", "shipments", "trip_outcomes", "vehicles", "products", "driver_notes"):
        assert name in a.tables and name in b.tables
        assert set(a.tables[name]["columns"]) == set(b.tables[name]["columns"])


@pytest.mark.parametrize("sql", [RETURNED, OPEN])
def test_the_same_sql_runs_on_both_companies(world, sql):
    for company in ("T01", "T02"):
        rows = run_reference_sql(world, company, sql)
        assert len(rows) == 1 and isinstance(rows[0][0], int) and rows[0][0] >= 0


def test_every_template_row_runs_on_both_companies(world):
    rows = [json.loads(line) for line in TEMPLATE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    for q in rows:
        for company in ("T01", "T02"):
            out = run_reference_sql(world, company, q["answer_sql"])
            assert isinstance(out, list), (q["id"], company)


@pytest.mark.parametrize("sql", [
    "delete from orders",
    "update orders set status='open'",
    "insert into orders(order_id) values ('X')",
    "create table x(a)",
    "drop table orders",
    "attach database ':memory:' as other",
    "pragma table_info(orders)",
    "select 1; delete from orders",
    "select * from sqlite_master",
])
def test_anything_but_one_read_only_select_is_refused(world, sql):
    before = run_reference_sql(world, "T01", "select count(*) from orders")
    with pytest.raises(QueryError):
        run_reference_sql(world, "T01", sql)
    assert run_reference_sql(world, "T01", "select count(*) from orders") == before


@pytest.mark.skipif(not (SEED7919 / "manifest.json").exists(), reason="full_seed7919 is not built locally")
def test_figures_checked_by_hand_on_full_seed7919():
    """The owner checked these against the canonical tables of world full_seed7919."""
    jangaon = ("select coalesce(sum(t.returned_cases),0) from trip_outcomes t join sites s using(site_id) "
               "where s.town='Jangaon' and substr(t.arrived_at,6,2)='09'")
    got = {c: (run_reference_sql(SEED7919, c, jangaon)[0][0], run_reference_sql(SEED7919, c, OPEN)[0][0])
           for c in ("T01", "T02")}
    print("full_seed7919 (returned cases in Jangaon in September, open orders):", got)
    assert got == {"T01": (619, 14), "T02": (87, 10)}
