"""What shows each agent and the whole system improving: the paired test scores right answers, each agent has totals and scores by
version, agents practise on their own, the Lesson Miner gets work, and EXP-014's whole protocol runs on a scripted model. No credits."""

import importlib.util
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from anubhav import events, muse, review, trace
from anubhav.agents import team
from anubhav.api import app as api_app
from anubhav.data import generate
from anubhav.harness import loop, practice
from anubhav.harness.store import HarnessStore
from anubhav.learning.store import LessonStore
from anubhav.muse import MockClient, ModelResponse, mock_final, mock_tool_call
from anubhav.runtime.broker import Session
from anubhav.runtime.company import CompanyData
from anubhav.service import runs as run_store, session
from anubhav.service.session import SUGGESTIONS, Workspace
from anubhav.ui import logs

spec = importlib.util.spec_from_file_location("exp014", "scripts/exp014_curve.py")
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


def row(bc, cc, be=0, ce=0, by=None):
    m = lambda e: {"tool_errors": e, "errors_by_agent": by or {}, "drafts": [], "cost_usd": 0.01, "tool_calls": 1}
    return {"request": "r", "expects_draft": False, "base": m(be), "cand": m(ce), "base_correct": bc, "cand_correct": cc}


# ---------- the paired test
def test_a_cheaper_change_that_loses_right_answers_fails():
    g = loop.gate([row(True, False, be=2, ce=0)], [])
    assert not g["pass"] and any("fewer correct answers" in r for r in g["reasons"]) and g["answers"] == {"base": 1, "cand": 0, "of": 1}


def test_more_right_answers_pass_even_with_the_same_errors():
    assert loop.gate([row(False, True)], [])["pass"]


def test_same_answers_need_fewer_errors_to_pass():
    assert loop.gate([row(True, True, be=1, ce=0)], [])["pass"]
    assert not loop.gate([row(True, True)], [])["pass"]


def test_rows_without_a_score_behave_as_before():
    plain = {"request": "r", "expects_draft": False, "base": {"tool_errors": 1, "drafts": [], "cost_usd": 0.01}, "cand": {"tool_errors": 0, "drafts": [], "cost_usd": 0.01}}
    g = loop.gate([plain], [])
    assert g["pass"] and g["answers"]["of"] == 0


def test_team_probe_counts_right_answers(C):
    d = mock_tool_call("delegate", {"agent": "analyst", "brief": "Count our sites in each town please."}, call_id="d")
    client = MockClient([d, mock_final("x"), mock_final("wrong"), d, mock_final("x"), mock_final("right")])
    case = {"request": "q", "company": "T01", "origin": "t", "expects_draft": False, "score": lambda r: r["reply"] == "right"}
    (r,) = loop.team_probe(C, client, None, [case], "analyst", {}, {"response_guidelines": ["x"]}, {}, lambda c: ([], [], []))["rows"]
    assert (r["base_correct"], r["cand_correct"]) == (False, True)


# ---------- totals and scores per agent
def test_each_agents_totals_are_its_own(C):
    resp = lambda m: ModelResponse(m, [], "stop", "mock", cost_usd=0.02)
    d = ModelResponse(None, mock_tool_call("delegate", {"agent": "analyst", "brief": "Find this order and return it please."}).tool_calls, "tool_calls", "mock", cost_usd=0.01)
    g = ModelResponse(None, mock_tool_call("get_order", {"order_id": "NOPE"}).tool_calls, "tool_calls", "mock", cost_usd=0.03)
    r = team.run(C, Session("T01"), MockClient([d, g, resp("none"), resp("ledu")]), "order?")
    t = {x["agent"]: x for x in logs.agent_totals([r])}
    assert t["analyst"]["tool_errors"] == 1 and t["analyst"]["cost_usd"] == pytest.approx(0.05)
    assert t["planner"]["cost_usd"] == pytest.approx(0.03) and t["planner"]["tool_calls"] == 1


def test_scores_are_kept_by_agent_and_version(tmp_path):
    H = HarnessStore(tmp_path / "h.sqlite")
    H.add_score("analyst", "analyst-000", "held", 10, 6)
    H.add_score("analyst", "analyst-001", "held", 10, 8)
    H.add_score("tool_forge", "tool_forge-000", "held", 10, 5)
    assert [s["correct"] for s in H.scores("analyst")] == [6, 8] and len(H.scores()) == 3


def test_an_agent_practises_on_its_own_and_is_scored(C):
    qs = practice.build(C, split="dev")[:2]
    client = MockClient([mock_final("x"), mock_final("y")])
    res = practice.run_agent(C, client, qs, "analyst")
    assert len(res) == 2 and "You are the Analyst" in client.calls[0]["messages"][0]["content"]
    assert practice.summary(res)["questions"] == 2


# ---------- the Lesson Miner gets work, and its proposals show live
def test_mine_with_agent_proposes_through_the_gate_and_streams_it(world, tmp_path, monkeypatch):
    d = tmp_path / "traces"
    d.mkdir()
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    monkeypatch.setattr(session.harness_store, "__defaults__", (tmp_path / "h.sqlite",))
    w = tmp_path / "w"
    shutil.copytree(world, w)
    ws = Workspace("minr", False, {}, w)
    C = ws.company("T01")
    site = next(s for s in C.sites.values() if s["name"] == "Lakshmi Agencies")
    r = run_store.mine_with_agent(ws, MockClient([
        mock_tool_call("records_digest", {}),
        mock_tool_call("propose_lesson", {"kind": "site_access", "params": {"site_id": site["site_id"], "max_length_ft": 22}, "claim": "gate", "evidence": ["3"]}),
        mock_final("one")]), "T01")
    assert r["agent_id"] == "lesson_miner"
    learned = [e for e in events.from_run(r) if e["type"] == "learning_event"]
    assert learned and learned[0]["payload"]["agent"] == "lesson_miner" and learned[0]["payload"]["decision"] == "proposed"
    assert not ws.store().list("T01", {"ACTIVE_POLICY", "ACTIVE_ADVISORY"})


# ---------- the review reports per agent
def test_nightly_review_reports_problems_per_agent(C, tmp_path):
    bad = [mock_tool_call("get_order", {"order_id": "NOPE"}, call_id=f"g{i}") for i in range(2)]
    r = team.run(C, Session("T01"), MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Find this order and return it please."}), *bad, mock_final("no"), mock_final("ledu")]), "order?")
    rep = review.review(C, LessonStore(tmp_path / "l.sqlite"), [r | {"saved_at": "2026-10-01T10:00:00"}], [])
    assert rep["by_agent"]["analyst"]["issues"] and not rep["by_agent"]["planner"]["issues"]


# ---------- replays prefer the same way of working
def test_replay_prefers_learned_tools_then_team_or_single(world):
    ws = Workspace("x", True, {}, world)
    req = SUGGESTIONS["New tool"]
    assert run_store.find_replay(ws, "T01", req, False, learned=True, team=True)["tool_calls"] == 1     # tools outrank mode


@pytest.fixture
def api_env(world, tmp_path, monkeypatch):
    for k in muse.KEYS.values():
        monkeypatch.delenv(k, raising=False)
    d = tmp_path / "traces"
    d.mkdir()
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    monkeypatch.setattr(session.harness_store, "__defaults__", (tmp_path / "h.sqlite",))
    w = tmp_path / "w"
    shutil.copytree(world, w)
    return TestClient(api_app.create_app(public=True, world=w, replay_pace=0), raise_server_exceptions=False)


def test_compare_shows_a_request_before_and_after_learning(api_env):
    body = api_env.get("/api/compare", params={"company": "T01", "request": SUGGESTIONS["Roman Telugu"]}).json()
    assert body["cold"]["lessons_in_prompt"] == 0 and body["with_lessons"]["lessons_in_prompt"] > 0
    assert body["cold"]["drafts"][0]["vehicle_id"] != body["with_lessons"]["drafts"][0]["vehicle_id"]
    tools = api_env.get("/api/compare", params={"company": "T01", "request": SUGGESTIONS["New tool"]}).json()
    assert tools["cold"]["tool_calls"] > tools["with_learned_tools"]["tool_calls"] == 1


def test_agent_detail_has_scores_and_the_curve_says_when_unmeasured(api_env, monkeypatch):
    d = api_env.get("/api/agents/analyst").json()
    assert d["scores"] == [] and "paired_tests" in d
    from anubhav.service import proof
    monkeypatch.setattr(proof, "_latest", lambda f, p: (None, None))
    assert api_env.get("/api/proof/curve").json()["measured"] is False


def test_tool_check_says_who_named_it_and_stays_free_on_the_public_host(api_env):
    g = next(x for x in api_env.get("/api/tools/candidates").json() if x["reached_threshold"])
    t = api_env.post(f"/api/tools/candidates/{g['key']}/check", json={}).json()
    assert t["named_by"] == "code"
    assert api_env.get("/api/session").json()["live_runs_left"] == session.LIVE_RUNS_PER_SESSION


# ---------- EXP-014, end to end on a scripted model
class Scripted:
    """Answers every question the same way, so the whole protocol can run without a model."""
    model = "scripted"

    def chat(self, messages, tools=None, **kw):
        return ModelResponse('{"lessons": []}', [], "stop", "scripted", cost_usd=0.001)


def test_exp014_runs_end_to_end_and_resumes_without_paying_twice(world, tmp_path):
    res = exp.experiment(world, tmp_path, Scripted(), Scripted(), "t")
    assert [s["stage"] for s in res["stages"]] == ["s0_cold", "s1_lessons", "s2_pack", "s3_tools", "s4_changes"]
    assert res["decision"]["complete"] and set(res["agents"]) == {"planner", "analyst", "tool_forge", "lesson_miner"}
    assert (tmp_path / "exp014_t.json").exists()
    json.dumps(res, default=str)
    spent = res["cost_usd"]
    again = exp.experiment(world, tmp_path, Scripted(), Scripted(), "t")
    assert again["cost_usd"] == pytest.approx(spent)


def test_exp014_budget_stop(world, tmp_path):
    with pytest.raises(SystemExit, match="budget"):
        exp.experiment(world, tmp_path, Scripted(), Scripted(), "b", budget=0.005)


def test_exp014_rules():
    st = lambda name, **k: {"stage": name, "unsafe": 0, "rate": 0.5, "unwritten": 0.5, "new_company": 0.4, "gap": 0.5, "gap_mean_cost": 0.1, "learned_tool_used": 0, "gap_n": 10, **k}
    stages = [st("s0_cold", unwritten=0.3, rate=0.4, unsafe=3), st("s1_lessons", unwritten=0.8, new_company=0.3), st("s2_pack", new_company=0.9), st("s3_tools", learned_tool_used=6, gap_mean_cost=0.07), st("s4_changes", rate=0.6)]
    d = exp.decide(stages, {"analyst": {"gain_pts": 10}}, 0, 2)
    assert d["S1_safety"] and d["S2_lessons"] and d["S3_pack"] and d["S4_tools"] and d["S5_changes"] and d["whole_system_gain_pts"] == 20.0
    assert not exp.decide(stages, {"analyst": {"gain_pts": 0}}, 0, 2)["S5_changes"]
    assert not exp.decide(stages, {}, 1, 0)["S3_pack"]
    assert exp.decide(stages[:2], {}, 0, 0) == {"complete": False}
