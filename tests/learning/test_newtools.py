"""New tools from the agent's own queries (D-040, C3–C5): a query reused for different requests becomes a candidate;
code checks it (same rows, held-out values); only a person can make it active; then the broker offers it."""

import json

import pytest

from anubhav.data import generate
from anubhav.learning import newtools as nt
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import Sandbox

Q = ("SELECT COUNT(*) AS returned FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id "
     "WHERE s.town = '{town}' AND t.status = 'returned' AND t.arrived_at BETWEEN '{a}' AND '{b}'")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


def run_with(sql, request, rows=1, company="T01", run_id="r"):
    return {"run_id": run_id, "company": company, "request": request, "trace": [
        {"type": "tool", "name": "run_query", "ok": True, "arguments": json.dumps({"sql": sql, "purpose": "returned stops in a town in a month"}),
         "result": {"row_count": rows}}]}


def three_runs(C):
    towns = sorted({s["town"] for s in C.sites.values()})
    return [run_with(Q.format(town=towns[0], a="2026-09-01", b="2026-09-30"), f"{towns[0]} lo September returns?", run_id="r1"),
            run_with(Q.format(town=towns[1], a="2026-08-01", b="2026-08-31"), f"How many returns in {towns[1]} in August?", run_id="r2"),
            run_with(Q.format(town=towns[2], a="2026-10-01", b="2026-10-15"), f"{towns[2]} returns this month?", run_id="r3")]


def test_dates_and_names_become_parameters_but_codes_and_labels_do_not(C):
    sb = Sandbox(C)
    tpl, ps = nt.template("select case w when '2' then 'Tuesday' end, count(*) from trip_outcomes t join sites s using(site_id) "
                          "where s.town = 'Jangaon' and t.status = 'returned' and t.arrived_at between '2026-09-01' and '2026-09-30'", sb)
    assert [p["name"] for p in ps] == ["town", "date_from", "date_to"]
    assert "'Tuesday'" in tpl and "'returned'" in tpl and ":town" in tpl


def test_a_query_reused_for_different_requests_is_a_candidate(C):
    sb = Sandbox(C)
    runs = three_runs(C)
    assert [len(g["uses"]) for g in nt.candidates(runs, "T01", sb)] == [3]
    assert nt.candidates(runs[:2], "T01", sb) == []                       # used for two requests: not yet
    assert nt.candidates(runs, "T02", sb) == []                           # another company's runs never count
    one = nt.uses_in(runs[:1], "T01", sb)[0]
    assert len(nt.candidates(runs[:1], "T01", sb, marked={one["key"]})) == 1   # unless a person marks it


def test_checks_pass_for_a_general_query_and_fail_for_a_one_off(C):
    sb = Sandbox(C)
    g = nt.candidates(three_runs(C), "T01", sb)[0]
    c = nt.check(g, sb)
    assert c["pass"] and all(x["same"] for x in c["same_rows"]) and len(c["held_out"]) == nt.HELD_OUT
    held = {h["values"]["town"] for h in c["held_out"]}
    assert not held & {p["value"] for u in g["uses"] for p in u["params"]}       # held-out towns are new
    site = next(iter(C.sites.values()))                 # a town AND one site in it: other values rarely match
    one_off = f"SELECT name FROM sites WHERE town = '{site['town']}' AND site_id = '{site['site_id']}'"
    g2 = nt.candidates([run_with(one_off, "a"), run_with(one_off, "b"), run_with(one_off, "c")], "T01", sb)[0]
    assert "finds nothing for most held-out values: it only fits the original case" in nt.check(g2, sb)["reasons"]
    bad = dict(g, template=g["template"].replace("'returned'", "'delivered'"))
    assert "with the original values it does not give the original answers" in nt.check(bad, sb)["reasons"]


def test_only_a_person_activates_a_tool_and_only_if_its_checks_passed(C, tmp_path):
    S, sb = LessonStore(tmp_path / "l.sqlite"), Sandbox(C)
    g = nt.candidates(three_runs(C), "T01", sb)[0]
    tid = nt.propose(S, "T01", g, nt.check(g, sb), nt.suggest_name(g), "Returned stops in a town over a date range")
    assert nt.tools(S, "T01", "active") == []
    with pytest.raises(PermissionError):
        nt.decide(S, tid, "", True)
    bad = nt.propose(S, "T01", dict(g, key="ffffffffffff"), {"pass": False}, "other_tool", "x")
    with pytest.raises(PermissionError):
        nt.decide(S, bad, "owner", True)
    assert nt.decide(S, tid, "owner", True) == "active"
    with pytest.raises(ValueError):
        nt.propose(S, "T01", g, {"pass": True}, nt.suggest_name(g), "duplicate name")
    assert nt.decide(S, tid, "owner", False) == "retired" and nt.tools(S, "T01", "active") == []


def test_the_broker_offers_an_approved_tool_and_it_gives_the_original_answer(C, tmp_path):
    S, sb = LessonStore(tmp_path / "l.sqlite"), Sandbox(C)
    g = nt.candidates(three_runs(C), "T01", sb)[0]
    tid = nt.propose(S, "T01", g, nt.check(g, sb), "returned_in_town", "Returned stops in a town over a date range")
    nt.decide(S, tid, "owner", True)
    b = Broker(C, Session("T01", "viewer"), learned_tools=nt.tools(S, "T01", "active"))
    assert "returned_in_town" in {t["function"]["name"] for t in b.openai_tools()}
    u = g["uses"][0]
    r = b.call("returned_in_town", {p["name"]: p["value"] for p in u["params"]})
    assert r["ok"] and r["result"]["rows"] == sb.run(u["sql"])["rows"]
    assert b.call("returned_in_town", {"town": "x", "date_from": "2026-02-30", "date_to": "2026-03-01"})["error"]["code"] == "BAD_ARGS"
    assert b.call("returned_in_town", {"town": "x"})["error"]["code"] == "BAD_ARGS"            # missing parameters
    plain = Broker(C, Session("T01"))
    assert "returned_in_town" not in {t.name for t in plain.list_tools()}                        # only when given


def test_differently_written_queries_with_the_same_answers_are_one_tool(C):
    sb = Sandbox(C)
    town = sorted({s["town"] for s in C.sites.values()})
    a = ("SELECT strftime('%w', sh.delivery_date) AS w, COUNT(*) AS stops FROM trip_outcomes t JOIN shipments sh USING (shipment_id) "
         "JOIN sites s ON s.site_id = t.site_id WHERE s.town = '{}' GROUP BY 1 ORDER BY 2 DESC")
    b = ("SELECT CASE strftime('%w', sh.delivery_date) WHEN '6' THEN 'శనివారం' ELSE 'other' END AS రోజు, COUNT(*) AS n, "
         "strftime('%w', sh.delivery_date) AS wn FROM sites s JOIN trip_outcomes t ON t.site_id = s.site_id "
         "JOIN shipments sh ON sh.shipment_id = t.shipment_id WHERE s.town = '{}' GROUP BY wn")
    orders = ("SELECT strftime('%w', o.delivery_date) AS w, COUNT(*) AS n FROM orders o JOIN sites s ON s.site_id = o.site_id "
              "WHERE s.town = '{}' GROUP BY 1")
    runs = [run_with(a.format(town[0]), "busiest day A?", run_id="1"), run_with(b.format(town[1]), "రద్దీ రోజు B?", run_id="2"),
            run_with(a.format(town[3]), "busiest day D?", run_id="4")]
    (g,) = nt.candidates(runs, "T01", sb)
    assert len(g["uses"]) == 3 and g["template"].isascii() and nt.check(g, sb)["pass"]
    runs.append(run_with(orders.format(town[2]), "orders by day C?", run_id="3"))           # counts orders, not stops
    assert [len(x["uses"]) for x in nt.candidates(runs, "T01", sb)] == [3]


def test_names_and_descriptions_are_general_never_the_values_a_tool_was_built_from(C, tmp_path):
    sb = Sandbox(C)
    g = nt.candidates(three_runs(C), "T01", sb)[0]
    name, desc = nt.suggest_name(g), nt.describe(g)
    assert name == "returned_by_town_and_dates" and not nt.specific_words(g, name + " " + desc)
    assert "town (town)" in desc and "<town>" in desc
    S = LessonStore(tmp_path / "l.sqlite")
    town = g["uses"][0]["params"][0]["value"]
    with pytest.raises(ValueError):
        nt.propose(S, "T01", g, {"pass": True}, f"returns_{town.lower()}_september", desc)
    nt.propose(S, "T01", g, {"pass": True}, name, desc)
    assert nt.free_name(S, "T01", name) == f"{name}_2"
