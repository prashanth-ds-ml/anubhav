"""Multi-agent mode (D-044): the roster, delegate with its limits, retries, find_capability, sequence_stops, and the
event stream. Mock model only; no credits. The single-Planner baseline must stay exactly as it was."""

import json
from dataclasses import replace

import pytest

from anubhav import events
from anubhav.agent import graph
from anubhav.agents import registry, team
from anubhav.data import generate
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData


@pytest.fixture(scope="session")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


def delegate(agent, brief="Count our sites in each town and return the counts."):
    return mock_tool_call("delegate", {"agent": agent, "brief": brief}, call_id=f"d_{agent}")


def run_team(C, script, **kw):
    return team.run(C, Session("T01", "dispatcher", "demo"), MockClient(script), "Mana sites enni unnayi?", **kw)


# ---------- roster
def test_roster_is_data_with_one_lead():
    r = registry.load()
    assert r.lead().agent_id == "planner"
    assert {a.agent_id for a in r.active()} == {"planner", "analyst"}
    assert {"tool_forge", "lesson_miner"} <= set(r.agents)
    assert all(a.purpose and a.instructions for a in r.agents.values())


def test_roster_refuses_two_voices(tmp_path):
    p = tmp_path / "agents.yaml"
    p.write_text("agents:\n  a: {name: A, purpose: x, instructions: y, voice: true}\n  b: {name: B, purpose: x, instructions: y, voice: true}\n")
    with pytest.raises(ValueError):
        registry.load(p)


# ---------- the baseline is untouched
def test_single_planner_baseline_has_no_team_tools_or_tags(C):
    b = Broker(C, Session("T01"))
    assert not {"delegate", "find_capability", "sequence_stops"} & set(b.tools)
    assert "agents" not in b.call("discover_capabilities", {})["result"]
    r = graph.run(b, MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "sites?")
    assert "agent_id" not in r and all("agent_id" not in s and "attempt" not in s for s in r["trace"])


# ---------- delegation
def test_planner_delegates_to_the_analyst_and_gets_the_answer(C):
    r = run_team(C, [delegate("analyst"), mock_tool_call("list_sites", {}), mock_final("45 sites in 9 towns"),
                     mock_final("Mana daggara 45 sites unnayi")])
    assert r["mode"] == "team" and r["agent_id"] == "planner" and r["depth"] == 0
    assert r["reply"] == "Mana daggara 45 sites unnayi"
    (child,) = r["children"]
    assert (child["agent_id"], child["depth"], child["caller"]) == ("analyst", 1, "planner")
    assert child["reply"] == "45 sites in 9 towns" and child["request"].startswith("Count our sites")
    step = next(s for s in r["trace"] if s["type"] == "tool" and s["name"] == "delegate")
    assert step["ok"] and step["result"]["run_id"] == child["run_id"] and step["agent_id"] == "planner"
    assert all(s["agent_id"] == "analyst" and s["depth"] == 1 for s in child["trace"])
    who = {row["user"] for row in C.runtime.audit_rows()}
    assert {"demo@planner", "demo@analyst"} <= who


def test_teammate_prompt_is_its_own_and_lead_prompt_lists_the_team(C):
    client = MockClient([delegate("analyst"), mock_final("done"), mock_final("ok")])
    team.run(C, Session("T01"), client, "x")
    lead_sys, child_sys = client.calls[0]["messages"][0]["content"], client.calls[1]["messages"][0]["content"]
    assert "analyst (Analyst)" in lead_sys and "dispatch-planning assistant" in lead_sys
    assert child_sys.startswith("You are the Analyst of T01") and "dispatch-planning assistant" not in child_sys
    assert "planner (Planner)" in child_sys


@pytest.mark.parametrize("agent,code", [("planner", "DELEGATION_LIMIT"), ("nobody", "NOT_FOUND"), ("tool_forge", "NOT_FOUND")])
def test_delegate_refuses_self_unknown_and_planned_agents(C, agent, code):
    r = run_team(C, [delegate(agent), mock_final("ok")])
    step = next(s for s in r["trace"] if s["type"] == "tool")
    assert not step["ok"] and step["error"]["code"] == code and r["children"] == []


def test_delegation_depth_is_capped(C):
    roster = replace(registry.load(), max_depth=1)
    r = run_team(C, [delegate("analyst"), delegate("planner", "Plan the Jangaon orders for tomorrow please."),
                     mock_final("could not hand off"), mock_final("ok")], roster=roster)
    inner = next(s for s in r["children"][0]["trace"] if s["type"] == "tool")
    assert inner["error"]["code"] == "DELEGATION_LIMIT" and "deep" in inner["error"]["message"]


def test_shared_budget_used_up_refuses_delegation(C):
    t = team.Team(registry.load(), MockClient([]), max_usd=0.10)
    t.spent = 0.098                 # teammates already spent almost all of it
    b = Broker(C, Session("T01", agent="planner"), team=t)
    out = b.call("delegate", {"agent": "analyst", "brief": "Count our sites in each town please."})
    assert out["error"]["code"] == "DELEGATION_LIMIT" and "budget" in out["error"]["message"] and t.children == []


def test_partial_teammate_answer_is_flagged(C):
    analyst = replace(registry.load().get("analyst"), limits=graph.Limits(max_turns=2, max_tool_calls=1, max_usd=0.1))
    roster = registry.load()
    roster = replace(roster, agents={**roster.agents, "analyst": analyst})
    r = run_team(C, [delegate("analyst"), mock_tool_call("list_sites", {}), mock_final("partial"), mock_final("ok")], roster=roster)
    step = next(s for s in r["trace"] if s["type"] == "tool")
    assert r["children"][0]["stop"] == "limit" and "partial" in step["result"]["note"]


# ---------- retries
def test_a_failing_tool_gets_three_attempts_then_must_change_course(C):
    bad = [mock_tool_call("get_order", {"order_id": f"NOPE-{i}"}, call_id=f"g{i}") for i in range(4)]
    r = run_team(C, bad + [mock_final("order dorakaledu")])
    steps = [s for s in r["trace"] if s["type"] == "tool"]
    assert [s.get("attempt", 1) for s in steps] == [1, 2, 3, 4]
    assert [s["error"]["code"] for s in steps] == ["NOT_FOUND"] * 3 + ["RETRY_LIMIT"]


# ---------- finding a capability
def test_find_capability_ranks_tools_and_teammates(C):
    b = Broker(C, Session("T01", agent="planner"), analysis=True, team=team.Team(registry.load(), None))
    res = b.call("find_capability", {"need": "past trips and delivery history"})["result"]
    assert res["matches"] and res["matches"][0]["name"] == "trip_history" and "tool_missing" not in res
    res = b.call("find_capability", {"need": "records and questions"})["result"]
    assert any(m["kind"] == "agent" and m["name"] == "analyst" for m in res["matches"])


def test_find_capability_says_plainly_when_nothing_fits(C):
    b = Broker(C, Session("T01", agent="planner"), analysis=True, team=team.Team(registry.load(), None))
    res = b.call("find_capability", {"need": "xylophone quantum"})["result"]
    assert res["matches"] == [] and res["tool_missing"] and "run_query" in res["next_step"]


def test_discover_capabilities_lists_teammates_in_team_mode(C):
    b = Broker(C, Session("T01", agent="planner"), team=team.Team(registry.load(), None))
    agents = {a["agent"]: a for a in b.call("discover_capabilities", {})["result"]["agents"]}
    assert agents["analyst"]["available"] and not agents["planner"]["available"] and not agents["tool_forge"]["available"]


# ---------- route order (estimate)
def test_sequence_stops_orders_nearest_town_first(C):
    b = Broker(C, Session("T01", agent="planner"), team=team.Team(registry.load(), None))
    ids = list(C.sites)[:6]
    r = b.call("sequence_stops", {"site_ids": ids})["result"]
    assert sorted(s["site_id"] for s in r["stops"]) == sorted(ids) and "not optimized" in r["method"]
    totals = [s["total_km"] for s in r["stops"]]
    assert totals == sorted(totals) and r["total_km"] == totals[-1]
    assert b.call("sequence_stops", {})["error"]["code"] == "BAD_ARGS"
    assert b.call("sequence_stops", {"draft_id": "DR-NONE"})["error"]["code"] == "NOT_FOUND"


# ---------- events
def test_team_run_becomes_one_event_stream_with_the_handoff_nested(C, tmp_path):
    r = run_team(C, [delegate("analyst"), mock_tool_call("find_capability", {"need": "xylophone quantum"}),
                     mock_final("45 sites"), mock_final("45 sites unnayi")])
    ev = events.from_run(r)
    assert [e["seq"] for e in ev] == list(range(len(ev))) and {e["run_id"] for e in ev} == {r["run_id"]}
    assert all(e["type"] in events.TYPES for e in ev)
    kinds = [(e["type"], e["agent_id"], e["depth"]) for e in ev]
    assert kinds[0] == ("agent_start", "planner", 0) and kinds[-1] == ("agent_done", "planner", 0)
    h = kinds.index(("handoff", "planner", 0))
    assert kinds[h + 1] == ("agent_start", "analyst", 1) and ("agent_done", "analyst", 1) in kinds[h:]
    assert ("tool_missing", "analyst", 1) in kinds
    child_start = ev[h + 1]
    assert child_start["caller"] == "planner" and ev[h]["payload"]["to"] == "analyst"
    store = events.EventStore(tmp_path / "ev.sqlite")
    store.save(ev)
    assert store.load(r["run_id"]) == json.loads(json.dumps(ev)) and store.runs() == [r["run_id"]]
    assert [e["seq"] for e in store.load(r["run_id"], after=len(ev) - 3)] == [len(ev) - 2, len(ev) - 1]


def test_baseline_runs_convert_too(C):
    b = Broker(C, Session("T01"))
    r = graph.run(b, MockClient([mock_tool_call("get_order", {"order_id": "NOPE"}), mock_final("ledu")]), "order?")
    ev = events.from_run(r)
    assert [e["type"] for e in ev] == ["agent_start", "tool_call", "tool_result", "agent_done"]
    assert {e["agent_id"] for e in ev} == {"planner"} and ev[0]["caller"] == "person"


# ---------- the contract with the web app
def _schema():
    from anubhav.data.config import ROOT
    return json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))


def test_every_saved_demo_run_and_team_run_meets_the_event_contract(C):
    import jsonschema
    from anubhav.data.config import ROOT
    schema = _schema()
    runs = [json.loads(x) for x in (ROOT / "demo" / "replay_runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    runs.append(run_team(C, [delegate("analyst"), mock_tool_call("get_order", {"order_id": "NOPE"}),
                             mock_tool_call("get_order", {"order_id": "NOPE"}), mock_final("x"), mock_final("y")]))
    for r in runs:
        for e in events.from_run(r):
            jsonschema.validate(e, schema)


def test_committed_fixtures_meet_the_contract():
    import jsonschema
    from anubhav.data.config import ROOT
    schema = _schema()
    files = sorted((ROOT / "web" / "fixtures").glob("*.jsonl"))
    assert {f.stem for f in files} >= {"plain_plan", "handoff_analyst", "retry_tool_missing"}
    for f in files:
        ev = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert [e["seq"] for e in ev] == list(range(len(ev)))
        for e in ev:
            jsonschema.validate(e, schema)
