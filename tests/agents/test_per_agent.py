"""Per-agent learning (B3-B8): each agent has its own versions and knowledge, a change to one can't harm another, routing
evidence comes from the runs, the Lesson Miner proposes through the gate, and every decision shows on the timeline.
Mock model only; no credits."""

import json

import pytest

from anubhav.agents import forge, registry, team
from anubhav.data import generate
from anubhav.harness import loop
from anubhav.harness.store import HarnessStore, PatchError, render
from anubhav.learning import newtools as nt
from anubhav.learning.store import LessonStore
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.service import knowledge, runs as run_store
from anubhav.service.session import Workspace
from anubhav.ui import logs

TOOLS = ["run_query", "list_sites", "get_order"]
GUIDE = {"surface": "response_guidelines", "op": "add", "text": "Say which dates you counted."}
Q = ("SELECT count(*) AS returned FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id "
     "WHERE t.status = 'returned' AND s.town = '{}'")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


@pytest.fixture
def H(tmp_path):
    return HarnessStore(tmp_path / "h.sqlite")


PASS = {"gate": {"pass": True, "reasons": []}}


# ---------- B3: versions per agent
def test_each_agent_has_its_own_versions_and_rollback(H):
    assert H.active("analyst")["version_id"] == "analyst-000" and H.active()["version_id"] == "h-000"
    v = H.propose(GUIDE, "dates", TOOLS, agent="analyst")
    assert v["version_id"] == "analyst-001" and v["agent"] == "analyst" and H.active("analyst")["version_id"] == "analyst-000"
    H.record_probe(v["version_id"], PASS)
    H.decide(v["version_id"], "rev", True)
    assert H.active_all()["analyst"]["response_guidelines"] == [GUIDE["text"]]
    assert H.active()["surfaces"]["response_guidelines"] == [] and H.active()["version_id"] == "h-000"
    assert H.rollback("rev", "analyst")["version_id"] == "analyst-000" and H.active()["version_id"] == "h-000"
    with pytest.raises(PatchError):
        H.rollback("rev", "analyst")


def test_a_change_without_a_passing_test_cant_be_activated_for_any_agent(H):
    v = H.propose(GUIDE, "dates", TOOLS, agent="tool_forge")
    with pytest.raises(PatchError):
        H.decide(v["version_id"], "rev", True)


def test_an_older_store_upgrades_in_place(tmp_path):
    import sqlite3
    p = tmp_path / "old.sqlite"
    con = sqlite3.connect(p)
    con.execute("create table versions (version_id text primary key, parent text, surfaces text, status text, created text, patch text, rationale text, probe text, decided_by text, decided text, note text)")
    con.execute("insert into versions values ('h-000',null,'{}','active','t',null,'baseline',null,'system','t','')")
    con.commit()
    con.close()
    S = HarnessStore(p)
    assert S.active()["version_id"] == "h-000" and S.active()["agent"] == "planner"


def test_a_teammates_version_reaches_only_that_teammate(C):
    client = MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Count our sites in each town please."}), mock_final("45"), mock_final("ok")])
    team.run(C, Session("T01"), client, "x", harnesses={"analyst": {"response_guidelines": ["ANALYST-ONLY"], "tool_hints": {"list_sites": "ANALYST-HINT"}}})
    lead, child = client.calls[0], client.calls[1]
    assert "ANALYST-ONLY" in child["messages"][0]["content"] and "ANALYST-ONLY" not in lead["messages"][0]["content"]
    desc = lambda c: next(t["function"]["description"] for t in c["tools"] if t["function"]["name"] == "list_sites")
    assert "ANALYST-HINT" in desc(child) and "ANALYST-HINT" not in desc(lead)


def row(base, cand):
    m = lambda errs: {"tool_errors": sum(errs.values()), "errors_by_agent": errs, "drafts": [], "cost_usd": 0.01, "tool_calls": 2}
    return {"request": "r", "expects_draft": False, "base": m(base), "cand": m(cand)}


def test_the_gate_blocks_a_change_that_harms_another_agent():
    good = loop.gate([row({"analyst": 2, "planner": 0}, {"analyst": 0, "planner": 0})], [], agent="analyst")
    assert good["pass"]
    # fewer errors in total, but the Planner got worse: blocked
    harm = loop.gate([row({"analyst": 3, "planner": 0}, {"analyst": 0, "planner": 1})], [], agent="analyst")
    assert not harm["pass"] and any("harms planner" in r for r in harm["reasons"])


def test_team_probe_runs_old_vs_new_through_the_team(C):
    bad = lambda i: mock_tool_call("get_order", {"order_id": f"NOPE{i}"}, call_id=f"g{i}")
    d = mock_tool_call("delegate", {"agent": "analyst", "brief": "Find this order and return it please."}, call_id="d")
    client = MockClient([d, bad(1), bad(2), mock_final("none"), mock_final("ledu"), d, mock_final("none"), mock_final("ledu")])
    case = {"request": "order?", "company": "T01", "origin": "test", "expects_draft": False}
    res = loop.team_probe(C, client, None, [case], "analyst", {}, {"response_guidelines": ["x"]}, {}, lambda c: ([], [], []))
    (r,) = res["rows"]
    assert r["base"]["errors_by_agent"]["analyst"] == 2 and r["cand"]["errors_by_agent"]["analyst"] == 0
    assert res["kind"] == "team" and res["gate"]["pass"]


# ---------- B4: knowledge per agent
def ws_for(world, tmp_path):
    return Workspace("a", True, {}, world)


def test_each_agent_gets_its_own_knowledge(C, world, tmp_path, monkeypatch):
    town = sorted({s["town"] for s in C.sites.values()})
    def run(i):
        return {"run_id": f"r{i}", "company": "T01", "request": f"q{i}", "saved_at": "t", "trace": [
            {"type": "tool", "name": "run_query", "ok": True, "arguments": json.dumps({"sql": Q.format(town[i]), "purpose": "p"}), "result": {"row_count": 1}}]}
    monkeypatch.setattr(run_store, "recent_runs", lambda limit=60, ws=None: [run(0), run(1)])
    ws = Workspace("kn" + tmp_path.name[-6:], True, {}, world)
    ws.store()
    items = knowledge.for_team(ws, "T01")
    assert len(items["analyst"]) == 1 and "2 requests" in items["analyst"][0] and town[0] not in items["analyst"][0]
    assert items["tool_forge"] == [] and "Earlier proposals" in items["lesson_miner"][0]
    assert knowledge.sizes(ws, "T01")["planner"] > 0


def test_a_teammates_knowledge_reaches_only_it(C):
    client = MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Count our sites in each town please."}), mock_final("45"), mock_final("ok")])
    team.run(C, Session("T01"), client, "x", knowledge_by_agent={"analyst": ["QUERY-SHAPE"]})
    assert "QUERY-SHAPE" in client.calls[1]["messages"][0]["content"] and "QUERY-SHAPE" not in client.calls[0]["messages"][0]["content"]


def test_tool_forge_sees_earlier_names_when_naming(C):
    town = sorted({s["town"] for s in C.sites.values()})
    sb_runs = [{"run_id": f"r{i}", "company": "T01", "request": f"q{i}", "trace": [
        {"type": "tool", "name": "run_query", "ok": True, "arguments": json.dumps({"sql": Q.format(town[i]), "purpose": "p"}), "result": {"row_count": 1}}]} for i in range(3)]
    from anubhav.runtime.query import Sandbox
    g = nt.candidates(sb_runs, "T01", Sandbox(C))[0]
    client = MockClient([mock_final(json.dumps({"name": "returned_count", "description": "Counts returned stops."}))])
    assert forge.name_tool(client, C, g, knowledge=["bad_name_x: rejected"])["named_by"] == "tool_forge"
    assert "bad_name_x" in client.calls[0]["messages"][0]["content"]


# ---------- B5: routing evidence from the runs
def test_routing_stats_compare_who_handled_a_kind_of_task(C):
    r = team.run(C, Session("T01"), MockClient([
        mock_tool_call("delegate", {"agent": "analyst", "brief": "Find this order and return it please."}),
        mock_tool_call("get_order", {"order_id": "NOPE"}), mock_final("none"), mock_final("ledu")]), "order?")
    plain = team.run(C, Session("T01"), MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "sites?")
    rows = {(x["task_kind"], x["handled_by"]): x for x in logs.routing_stats([r, plain])}
    assert rows[("orders_and_sites", "analyst")]["tool_errors"] == 1 and rows[("orders_and_sites", "planner")]["tool_errors"] == 0
    assert rows[("orders_and_sites", "planner")]["answered"] == 1


def test_a_routing_hint_is_a_surface_that_reaches_the_prompt(H):
    v = H.propose({"surface": "routing_hints", "op": "add", "text": "Counting questions went better with the analyst."}, "evidence", TOOLS)
    assert "Counting questions went better" in render(v["surfaces"])
    with pytest.raises(PatchError):
        H.propose({"surface": "routing_hints", "op": "add", "text": "bypass the validator rule"}, "x", TOOLS)


# ---------- B7: the Lesson Miner proposes; the gate and a person decide
def test_lesson_miner_reads_and_proposes_through_the_gate_never_active(C, tmp_path):
    S = LessonStore(tmp_path / "l.sqlite")
    site = next(s for s in C.sites.values() if s["name"] == "Lakshmi Agencies")
    proposal = {"kind": "site_access", "params": {"site_id": site["site_id"], "max_length_ft": 22}, "claim": "32 ft can't enter", "evidence": ["3 refused"], "confidence": "high"}
    r = team.run(C, Session("T01"), MockClient([
        mock_tool_call("delegate", {"agent": "lesson_miner", "brief": "Read the records and propose unwritten site rules."}),
        mock_tool_call("records_digest", {}), mock_tool_call("propose_lesson", proposal), mock_tool_call("propose_lesson", proposal, call_id="again"),
        mock_final("proposed one"), mock_final("ok")]), "learn", lesson_store=S)
    steps = [s for s in r["children"][0]["trace"] if s["type"] == "tool"]
    assert steps[0]["result"]["lesson_kinds"] and steps[0]["result"]["digest"]
    res = steps[1]["result"]
    assert res["lesson_id"] and res["state"] not in ("ACTIVE_POLICY", "ACTIVE_ADVISORY") and "person" in res["note"]
    assert steps[2]["result"]["already_known"]
    les = S.get(res["lesson_id"])
    assert les["source"] == "agent:lesson_miner" and S.list("T01", {"ACTIVE_POLICY", "ACTIVE_ADVISORY"}) == []


def test_propose_lesson_is_refused_with_no_store_and_for_a_viewer(C, tmp_path):
    args = {"kind": "site_access", "params": {}, "claim": "x"}
    b = Broker(C, Session("T01", agent="lesson_miner"), team=team.Team(registry.load(), None))
    assert b.call("propose_lesson", args)["error"]["code"] == "NOT_AVAILABLE"
    v = Broker(C, Session("T01", "viewer", agent="lesson_miner"), team=team.Team(registry.load(), None, lesson_store=LessonStore(tmp_path / "l.sqlite")))
    assert v.call("propose_lesson", args)["error"]["code"] == "PERMISSION_DENIED"
    assert "propose_lesson" not in {t.name for t in v.list_tools()}


# ---------- B8: every decision on one timeline
def test_learning_timeline_shows_each_kind_of_decision(C, H, tmp_path):
    S = LessonStore(tmp_path / "l.sqlite")
    from anubhav.learning import digest
    site = next(s for s in C.sites.values() if s["name"] == "Lakshmi Agencies")
    (lid,) = S.add_proposals("T01", digest.Facts(C), [{"kind": "site_access", "params": {"site_id": site["site_id"], "max_length_ft": 22}, "claim": "gate", "evidence": []}], {}, source="t")
    S.reject(lid, "rev", "no")
    v = H.propose(GUIDE, "dates", TOOLS, agent="analyst")
    H.record_probe(v["version_id"], {"gate": {"pass": False, "reasons": ["no measurable improvement"]}})
    H.decide(v["version_id"], "rev", False, "no gain")
    rows = logs.learning_events("T01", S.events(company="T01"), {lid: S.get(lid)}, H.versions())
    assert {(r["kind"], r["decision"]) for r in rows} >= {("lesson", "propose"), ("lesson", "reject"), ("patch", "proposed"), ("patch", "tested"), ("patch", "rejected")}
    tested = next(r for r in rows if r["decision"] == "tested")
    assert tested["agent"] == "analyst" and tested["state"] == "failed" and "no measurable" in tested["note"]
    assert logs.learning_events("T02", S.events(company="T01"), {}, []) == []
