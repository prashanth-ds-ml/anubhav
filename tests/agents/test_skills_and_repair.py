"""Roles enforced in code, skills loaded on demand, learned tools re-checked, and Tool Forge repairing a tool that failed
its checks (owner, Nov 3). Mock model only; no credits."""

import json

import pytest

from anubhav.agents import forge, registry, team
from anubhav.data import generate
from anubhav.learning import newtools as nt
from anubhav.learning.store import LessonStore
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import Sandbox

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


def towns_of(C):
    return sorted({s["town"] for s in C.sites.values()})


def forge_run(C, town, request):
    return team.run(C, Session("T01", "dispatcher", "demo"), MockClient([
        mock_tool_call("delegate", {"agent": "tool_forge", "brief": f"Count the returned stops in {town}."}),
        mock_tool_call("run_query", {"sql": Q.format(town), "purpose": "returned stops in a town"}),
        mock_final("12"), mock_final("12 returned")]), request)


def group(C):
    t = towns_of(C)
    runs = [forge_run(C, t[i], f"returns in town {i}?") for i in range(3)]
    (g,) = nt.candidates(runs, "T01", Sandbox(C))
    return g


def member(C, agent):
    """A teammate's broker, as delegate builds it."""
    tm = team.Team(registry.load(), MockClient([]))
    return Broker(C, Session("T01", "dispatcher", "t", agent=agent), analysis=True, team=tm, depth=1)


# ---------- roles in code
def test_each_agent_may_call_only_its_own_tools(C):
    analyst, forge_b, miner, planner = (member(C, a) for a in ("analyst", "tool_forge", "lesson_miner", "planner"))
    denied = analyst.call("run_query", {"sql": "SELECT 1", "purpose": "x"})
    assert denied["error"]["code"] == "PERMISSION_DENIED" and "analyst may not call run_query" in denied["error"]["message"]
    assert analyst.call("list_sites", {})["ok"]
    assert "create_dispatch_draft" not in {t.name for t in analyst.list_tools()}
    assert planner.call("run_query", {"sql": "SELECT 1", "purpose": "x"})["error"]["code"] == "PERMISSION_DENIED"
    assert {"create_dispatch_draft", "delegate"} <= {t.name for t in planner.list_tools()}
    assert forge_b.call("run_query", {"sql": "SELECT 1 AS one", "purpose": "x"})["ok"]
    assert not {"create_dispatch_draft", "delegate", "propose_lesson"} & {t.name for t in forge_b.list_tools()}
    assert {"records_digest", "propose_lesson"} <= {t.name for t in miner.list_tools()}
    assert "create_dispatch_draft" not in {t.name for t in miner.list_tools()}
    alone = Broker(C, Session("T01", "dispatcher", "t"), analysis=True)          # single agent, frozen experiments: no list
    assert alone.call("run_query", {"sql": "SELECT 1 AS one", "purpose": "x"})["ok"]


# ---------- skills like Claude skills
def test_every_agent_has_skills_listed_in_its_prompt_and_loads_one_in_full(C):
    roster = registry.load()
    want = {"planner": "route-data-questions", "analyst": "hand-to-tool-forge", "tool_forge": "repair-a-tool", "lesson_miner": "revise-after-gate"}
    for agent, skill in want.items():
        assert roster.get(agent).skill(skill), (agent, skill)
    client = MockClient([mock_tool_call("load_skill", {"name": "route-data-questions"}), mock_final("ok")])
    r = team.run(C, Session("T01", "dispatcher", "t"), client, "how many tonnes this week?")
    system = client.calls[0]["messages"][0]["content"]
    assert "load_skill" in system and "route-data-questions:" in system
    step = next(s for s in r["trace"] if s["type"] == "tool" and s["name"] == "load_skill")
    assert step["ok"] and "Do not loop a per-item tool" in step["result"]["method"]
    wrong = member(C, "analyst").call("load_skill", {"name": "repair-a-tool"})       # another agent's skill
    assert wrong["error"]["code"] == "NOT_FOUND" and "answer-with-tools" in wrong["error"]["message"]


def test_skill_files_are_methods_not_business_facts():
    roster = registry.load()
    C_words = {"jangaon", "warangal", "lakshmi", "kazipet", "hanamkonda", "parkal"}
    for a in roster.agents.values():
        for s in a.skills:
            text = s.body().lower() + s.description.lower()
            assert not C_words & set(text.replace(",", " ").split()), (a.agent_id, s.name)


# ---------- Tool Forge repairs a tool that failed its checks
def fixed_date(g):
    return {**g, "template": g["template"] + " AND '2026-09-01' <= '2026-12-31'"}


def test_tool_forge_repairs_a_failed_tool_and_code_rechecks_it(C):
    g = group(C)
    bad = fixed_date(g)
    sb = Sandbox(C)
    failed = nt.check(bad, sb)
    assert not failed["pass"] and any("fixed date" in r for r in failed["reasons"])
    client = MockClient([mock_final(f"```sql\n{g['template']}\n```")])
    out = forge.repair_tool(client, C, bad, failed, sb)
    assert out["pass"] and out["template"] == g["template"] and len(out["attempts"]) == 1
    prompt = client.calls[0]["messages"][0]["content"]
    assert "fixed date" in prompt and ":" + g["uses"][0]["params"][0]["name"] in prompt


def test_a_repair_that_changes_the_inputs_or_is_not_a_select_is_refused_and_tries_stop_at_two(C):
    g = group(C)
    bad = fixed_date(g)
    sb = Sandbox(C)
    client = MockClient([mock_final("```sql\nSELECT count(*) FROM sites WHERE town = :place\n```"), mock_final("I can't fix this.")])
    out = forge.repair_tool(client, C, bad, nt.check(bad, sb), sb)
    assert not out["pass"] and len(out["attempts"]) == 2 and len(client.calls) == 2
    assert "inputs changed" in out["attempts"][0]["reasons"][0] and "not a SELECT" in out["attempts"][1]["reasons"][0]


def test_a_repair_must_still_give_the_original_answers(C):
    g = group(C)
    bad = fixed_date(g)
    sb = Sandbox(C)
    name = g["uses"][0]["params"][0]["name"]
    other = (f"SELECT count(*) AS returned FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id "
             f"WHERE t.status = 'delivered' AND s.town = :{name}")                       # general, but a different question
    out = forge.repair_tool(MockClient([mock_final(other), mock_final(other)]), C, bad, nt.check(bad, sb), sb)
    assert not out["pass"] and any("original answers" in r for r in out["checks"]["reasons"])


# ---------- health check on approved tools
def test_an_approved_tool_that_breaks_is_marked_for_repair_never_retired(C, tmp_path):
    g = group(C)
    sb, S = Sandbox(C), LessonStore(tmp_path / "l.sqlite")
    tid = nt.propose(S, "T01", g, nt.check(g, sb), "returned_stops_in_town", "Returned stops in a town")
    nt.decide(S, tid, "owner", True)
    assert nt.health(S, "T01", sb)[0]["ok"]
    with nt._con(S) as con:                                   # the records change under it: a column it reads is gone
        con.execute("update tools set template = replace(template, 't.status', 't.no_such_column') where tool_id = ?", (tid,))
    (h,) = nt.health(S, "T01", sb)
    assert not h["ok"] and "fails on its own example" in h["reasons"][0]
    t = nt.tools(S, "T01")[0]
    assert t["status"] == "active" and t["checks"]["health"]["ok"] is False


def test_failures_in_real_runs_count_but_a_budget_limit_does_not(C, tmp_path):
    g = group(C)
    sb, S = Sandbox(C), LessonStore(tmp_path / "l.sqlite")
    tid = nt.propose(S, "T01", g, nt.check(g, sb), "returned_stops_in_town", "Returned stops in a town")
    nt.decide(S, tid, "owner", True)
    run = {"company": "T01", "trace": [
        {"type": "tool", "name": "returned_stops_in_town", "ok": False, "error": {"code": "LIMIT", "message": "budget"}},
        {"type": "tool", "name": "returned_stops_in_town", "ok": False, "error": {"code": "BAD_ARGS", "message": "SQL error"}}]}
    (h,) = nt.health(S, "T01", sb, [run])
    assert not h["ok"] and h["reasons"] == ["failed 1 time(s) in real runs"]


def test_a_repaired_tool_goes_back_to_a_person(C, tmp_path):
    g = group(C)
    sb, S = Sandbox(C), LessonStore(tmp_path / "l.sqlite")
    bad = fixed_date(g)
    tid = nt.propose(S, "T01", bad, nt.check(bad, sb), "returned_stops_in_town", "Returned stops in a town")
    with pytest.raises(PermissionError):
        nt.decide(S, tid, "owner", True)                       # failed checks can't be approved
    out = forge.repair_tool(MockClient([mock_final(g["template"])]), C, bad, nt.check(bad, sb), sb)
    nt.revise(S, tid, out["template"], out["checks"], {"by": "tool_forge", "attempts": out["attempts"]})
    t = nt.tools(S, "T01")[0]
    assert t["status"] == "candidate" and t["checks"]["pass"] and t["checks"]["repair"]["by"] == "tool_forge"
    nt.decide(S, tid, "owner", True)
    assert nt.tools(S, "T01")[0]["status"] == "active"
    assert json.dumps(t["checks"])                              # stored whole, readable
