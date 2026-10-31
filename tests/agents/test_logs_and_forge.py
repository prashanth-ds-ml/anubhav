"""The logs are the base: team runs are saved whole, and everything that reads runs sees the teammates' steps. Then the
missing-tool flow on top of them: tool_missing -> Tool Forge -> query for 3+ requests -> candidate -> a person. Mock
model only; no credits."""

import json

import pytest

from anubhav import events, mcp_server, review, trace
from anubhav.agents import forge, registry, team
from anubhav.data import generate
from anubhav.harness import loop
from anubhav.learning import newtools as nt
from anubhav.learning.store import LessonStore
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import Sandbox
from anubhav.ui import logs

Q = ("SELECT count(*) AS returned FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id "
     "WHERE t.status = 'returned' AND s.town = '{}'")


@pytest.fixture(scope="session")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


def forge_run(C, town, request, need="busiest xylophone"):
    """The whole flow in one request: nothing fits -> Tool Forge -> one query -> answer -> reply."""
    return team.run(C, Session("T01", "dispatcher", "demo"), MockClient([
        mock_tool_call("find_capability", {"need": need}),
        mock_tool_call("delegate", {"agent": "tool_forge", "brief": f"Count the returned stops in {town} and return the number."}),
        mock_tool_call("run_query", {"sql": Q.format(town), "purpose": "returned stops in a town"}),
        mock_final("12 returned stops"), mock_final("12 returned")]), request)


def towns_of(C):
    return sorted({s["town"] for s in C.sites.values()})


# ---------- saved whole
def test_a_team_run_is_saved_with_its_teammates_and_events(C, tmp_path):
    r = forge_run(C, towns_of(C)[0], "returns?")
    trace.save(r, tmp_path, label="test")
    saved = trace.load(r["run_id"], tmp_path)
    assert [c["agent_id"] for c in saved["children"]] == ["tool_forge"]
    ev = events.EventStore(tmp_path / "events.sqlite").load(r["run_id"])
    assert {"tool_missing", "handoff"} <= {e["type"] for e in ev} and ev[0]["ts"] == saved["saved_at"]
    assert any("tool_forge: tool run_query" in x for x in trace.replay(r["run_id"], tmp_path))


def test_a_refused_fourth_attempt_is_not_shown_as_a_retry(C):
    bad = [mock_tool_call("get_order", {"order_id": "NOPE"}, call_id=f"g{i}") for i in range(4)]
    r = team.run(C, Session("T01"), MockClient(bad + [mock_final("ledu")]), "order?")
    assert [e["payload"]["attempt"] for e in events.from_run(r) if e["type"] == "retry"] == [2, 3]


# ---------- every reader sees the teammates
def test_timeline_issues_and_tool_usage_include_teammates(C):
    r = forge_run(C, towns_of(C)[0], "returns?")
    assert any(x.get("agent") == "tool_forge" and "run_query" in x["text"] for x in logs.timeline(r))
    use = {(u["agent"], u["tool"]): u for u in logs.tool_usage([r])}
    assert use[("tool_forge", "run_query")]["calls"] == 1 and use[("planner", "delegate")]["failed"] == 0
    (miss,) = logs.missing_tools([r])
    assert miss["need"] == "busiest xylophone" and miss["requests"] == ["returns?"]


def test_nightly_review_finds_problems_in_teammate_runs(C):
    bad = [mock_tool_call("get_order", {"order_id": "NOPE"}, call_id=f"g{i}") for i in range(2)]
    r = team.run(C, Session("T01"), MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Find order NOPE and return it."}),
                                                *bad, mock_final("no order"), mock_final("ledu")]), "order?")
    problems = loop.collect([r], [])
    assert any(i["kind"] == "tool_error" and i["tool"] == "get_order" for i in problems["trace_issues"])


# ---------- the missing-tool flow
def test_tool_missing_points_to_tool_forge_and_its_query_is_logged_as_its_own(C):
    r = forge_run(C, towns_of(C)[0], "returns?")
    first = next(s for s in r["trace"] if s["type"] == "tool")
    assert first["result"]["tool_missing"] and "tool_forge" in first["result"]["next_step"]
    (u,) = nt.uses_in([r], "T01", Sandbox(C))
    assert u["agent"] == "tool_forge" and u["request"] == "returns?"     # the person's request, not the brief


def test_tool_forge_itself_is_pointed_to_run_query_not_to_itself(C):
    b = Broker(C, Session("T01", agent="tool_forge"), analysis=True, team=team.Team(registry.load(), None), depth=1)
    res = b.call("find_capability", {"need": "xylophone quantum"})["result"]
    assert "run_query" in res["next_step"] and "tool_forge" not in res["next_step"]


def test_a_query_becomes_a_candidate_at_three_different_requests_not_before(C):
    sb, t = Sandbox(C), towns_of(C)
    two = [forge_run(C, t[0], "returns in A?"), forge_run(C, t[1], "returns in B?")]
    assert nt.candidates(two, "T01", sb) == []
    same_again = two + [forge_run(C, t[2], "returns in B?")]               # the same request again doesn't count
    assert nt.candidates(same_again, "T01", sb) == []
    three = two + [forge_run(C, t[2], "returns in C?")]
    (g,) = nt.candidates(three, "T01", sb)
    assert len(g["requests"]) == 3 and {u["agent"] for u in g["uses"]} == {"tool_forge"} and nt.check(g, sb)["pass"]


def test_queries_from_different_agents_count_together(C):
    t = towns_of(C)
    runs = [forge_run(C, t[0], "returns in A?"), forge_run(C, t[1], "returns in B?"),
            team.run(C, Session("T01"), MockClient([mock_tool_call("run_query", {"sql": Q.format(t[2]), "purpose": "returned"}),
                                                    mock_final("3")]), "returns in C?")]
    (g,) = nt.candidates(runs, "T01", Sandbox(C))
    assert {u["agent"] for u in g["uses"]} == {"tool_forge", "planner"}


def test_review_turns_it_into_a_candidate_a_person_must_approve(C, tmp_path):
    t, S = towns_of(C), LessonStore(tmp_path / "l.sqlite")
    runs = [forge_run(C, t[i], f"returns {i}?") | {"saved_at": f"2026-10-01T10:0{i}:00"} for i in range(3)]
    namer = MockClient([mock_final(json.dumps({"name": "returned_stops_in_town", "description": "Counts returned stops for a town."}))])
    rep = review.review(C, S, runs, [], forge_client=namer)
    (cand,) = rep["new_tools"]["candidates"]
    assert cand["named_by"] == "tool_forge" and cand["agents"] == ["tool_forge"] and cand["checks_passed"]
    assert rep["missing_tools"][0]["times"] == 3
    assert nt.tools(S, "T01", "active") == [] and nt.tools(S, "T01", "candidate")[0]["name"] == "returned_stops_in_town"


# ---------- Tool Forge names; code still decides
def group(C):
    t = towns_of(C)
    runs = [forge_run(C, t[i], f"returns {i}?") for i in range(3)]
    return nt.candidates(runs, "T01", Sandbox(C))[0], t


@pytest.mark.parametrize("reply,why", [
    ("not json", "no usable name"),
    (json.dumps({"name": "Bad Name", "description": "x"}), "no usable name"),
    (json.dumps({"name": "ok_name", "description": "y" * 201}), "no usable name"),
])
def test_an_unusable_name_falls_back_to_codes_name(C, reply, why):
    g, _ = group(C)
    out = forge.name_tool(MockClient([mock_final(reply)]), C, g)
    assert out["named_by"] == "code" and out["name"] == nt.suggest_name(g) and why in out["why"]


def test_a_name_that_leaks_a_value_or_a_failed_model_falls_back(C):
    g, t = group(C)
    leak = json.dumps({"name": "returned_stops", "description": f"Counts returned stops in {t[0]}."})
    out = forge.name_tool(MockClient([mock_final(leak)]), C, g)
    assert out["named_by"] == "code" and t[0].lower() in out["why"]
    assert forge.name_tool(MockClient([]), C, g)["named_by"] == "code"
    assert forge.name_tool(None, C, g)["named_by"] == "code"


# ---------- approved tools reach the MCP server
def test_the_mcp_server_offers_approved_tools(C, world, tmp_path):
    t = towns_of(C)
    S = LessonStore(tmp_path / "learning" / "demo.sqlite")
    g = nt.candidates([forge_run(C, t[i], f"returns {i}?") for i in range(3)], "T01", Sandbox(C))[0]
    tid = nt.propose(S, "T01", g, nt.check(g, Sandbox(C)), "returned_stops_in_town", "Counts returned stops for a town.")
    assert mcp_server.learned_for(tmp_path, "T01") == []                   # not until a person approves
    nt.decide(S, tid, "owner", True)
    (spec,) = mcp_server.learned_for(tmp_path, "T01")
    b = Broker(C, Session("T01"), learned_tools=[spec])
    assert "returned_stops_in_town" in {x.name for x in b.list_tools()}
    assert mcp_server.build_server(b) is not None
    assert mcp_server.learned_for(tmp_path / "nothing", "T01") == []
