"""Checks the model can't skip (from Meta's legal-agent workshop): a refused reply goes back, repeated refusals and open
questions stop the run for a person, the run resumes, and a person signs plans off. Mock model only; no credits."""

import json
import time

import jsonschema
import pytest
from fastapi.testclient import TestClient

from anubhav import events, muse, preflight, trace
from anubhav.agent import graph
from anubhav.agents import team
from anubhav.api import app as api_app, deps
from anubhav.data import generate
from anubhav.data.config import ROOT
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.service import checkpoints, session, stream

SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))
ASK = {"question": "Warangal lo ae site?"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


@pytest.fixture
def env(world, tmp_path, monkeypatch):
    d = tmp_path / "traces"
    d.mkdir()
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    session._harness.cache_clear()
    monkeypatch.setattr(session.harness_store, "__defaults__", (tmp_path / "harness.sqlite",))
    for k in muse.KEYS.values():
        monkeypatch.setenv(k, "test-key")
    session.shared_company.cache_clear()
    yield world
    session.shared_company.cache_clear()


def planner(C):
    return Broker(C, Session("T01", "dispatcher", "t"))


def script_model(monkeypatch, script):
    monkeypatch.setattr(muse, "client", lambda name="spark", **k: MockClient(script))


def wait(run_id):
    for _ in range(300):
        if stream.status(run_id).get("status") != "running":
            return stream.status(run_id)
        time.sleep(0.02)
    raise AssertionError("still running")


def one_draft(C):
    """A real order and a free vehicle that the validator accepts."""
    b = planner(C)
    for o in b.call("list_open_orders", {})["result"]["orders"]:
        for v in C.vehicles.values():
            out = b.call("create_dispatch_draft", {"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]})
            if out["ok"]:
                return o["order_id"], v["vehicle_id"], out["result"]["draft_id"]
    raise AssertionError("no valid draft in this world")


# ---------- the reply check sends the agent back
def test_a_refused_reply_goes_back_and_the_person_only_sees_the_fixed_one(C):
    client = MockClient([mock_final("Draft D-9999 is dispatched."), mock_final("I could not make a draft.")])
    r = graph.run(planner(C), client, "plan it", supervised=True)
    assert r["stop"] == "answered" and r["reply"] == "I could not make a draft." and r["reply_check"]["ok"]
    assert [s["attempt"] for s in r["trace"] if s["type"] == "reply_refused"] == [1]


def test_refused_ids_told_to_the_model_do_not_count_as_found(C):
    client = MockClient([mock_final("Use VH-777."), mock_final("Use VH-777."), mock_final("Use VH-777.")])
    r = graph.run(planner(C), client, "plan it", supervised=True)
    assert r["stop"] == "needs_person" and r["handoff"]["rule"] == "reply_refused"
    assert r["handoff"]["refused_reply"] == "Use VH-777." and r["reply"] == r["handoff"]["question"]
    assert not r["reply_check"]["ok"]


def test_unsupervised_runs_are_unchanged(C):
    """Frozen experiments: no extra tool, no extra model call, same stop."""
    r = graph.run(planner(C), MockClient([mock_final("Draft D-9999 is dispatched.")]), "plan it")
    assert r["stop"] == "answered" and not r["reply_check"]["ok"] and "checkpoint" not in r and "handoff" not in r


# ---------- stop and ask
def test_asking_needs_a_look_first_then_stops_with_no_more_model_calls(C):
    client = MockClient([mock_tool_call("ask_person", ASK), mock_tool_call("list_sites", {}), mock_tool_call("ask_person", ASK)])
    r = graph.run(planner(C), client, "Warangal load", supervised=True)
    asks = [s for s in r["trace"] if s["type"] == "tool" and s["name"] == "ask_person"]
    assert asks[0]["error"]["code"] == "LOOK_FIRST" and asks[1]["ok"]
    assert r["stop"] == "needs_person" and r["reply"] == ASK["question"] and r["handoff"]["rule"] == "question"
    assert "list_sites" in r["handoff"]["tools_used"] and len(client.calls) == 3


def test_a_teammate_cannot_ask_and_a_question_is_not_asked_twice(C):
    client = MockClient([mock_tool_call("list_sites", {}), mock_tool_call("ask_person", ASK)])
    first = graph.run(planner(C), client, "Warangal load", supervised=True)
    again = MockClient([mock_tool_call("ask_person", ASK), mock_final("Okay.")])
    r = graph.run(planner(C), again, "I don't know", supervised=True, resume=first["checkpoint"])
    assert r["trace"][1]["error"]["code"] == "ALREADY_ASKED" and r["stop"] == "answered"
    mate = MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Count the sites and return the number."}),
                       mock_final("3"), mock_final("3 sites")])
    team.run(C, Session("T01", "dispatcher", "t"), mate, "how many sites", supervised=True)
    teammate_tools = [t["function"]["name"] for t in mate.calls[1]["tools"]]
    lead_tools = [t["function"]["name"] for t in mate.calls[0]["tools"]]
    assert "ask_person" in lead_tools and "ask_person" not in teammate_tools


# ---------- repeated refusals go to a person
def test_three_refusals_stop_the_run_for_a_person(C):
    client = MockClient([mock_tool_call("get_order", {"order_id": f"NOPE{i}"}) for i in range(3)])
    r = graph.run(planner(C), client, "plan it", supervised=True)
    assert r["stop"] == "needs_person" and r["handoff"]["rule"] == "tool_refused" and r["handoff"]["tool"] == "get_order"
    assert r["tool_calls"] == 3 and len(client.calls) == 3


def test_a_stuck_teammate_stops_the_whole_request_and_events_match_the_saved_run(C):
    brief = {"agent": "analyst", "brief": "Find this order and return its site."}
    client = MockClient([mock_tool_call("delegate", brief)] + [mock_tool_call("get_order", {"order_id": f"NOPE{i}"}) for i in range(3)])
    live = []
    em = events.Emitter("x", sink=live.append)
    r = team.run(C, Session("T01", "dispatcher", "t"), client, "where is it", supervised=True, hooks=em, run_id="x")
    assert r["stop"] == "needs_person" and r["handoff"]["agent"] == "analyst" and r["children"][0]["stop"] == "needs_person"
    r.pop("checkpoint")
    saved = events.from_run(r)
    kinds = [e["type"] for e in saved]
    assert kinds.count("needs_person") == 2 and kinds[-1] == "agent_done"
    for e in saved:
        jsonschema.validate(e, SCHEMA)
    assert [(e["type"], e["agent_id"]) for e in live] == [(e["type"], e["agent_id"]) for e in saved]


def test_reply_refusals_appear_in_the_stream(C):
    r = graph.run(planner(C), MockClient([mock_final("VH-777"), mock_final("Sorry, none.")]), "plan it", supervised=True)
    checks = [e["payload"] for e in events.from_run({**r, "saved_at": None}) if e["type"] == "validator_check" and e["payload"]["tool"] == "reply_check"]
    assert checks == [{"tool": "reply_check", "pass": False, "attempt": 1, "of": 3, "unknown_ids": ["VH-777"], "claims": []}]


# ---------- sign-off
def test_approved_plans_keep_their_truck_and_only_a_person_can_release_them(C):
    order, vehicle, draft = one_draft(C)
    b = planner(C)
    assert C.runtime.decide(draft, "approve", "", "reviewer") and C.runtime.draft(draft)["status"] == "approved"
    day = C.runtime.draft(draft)["delivery_date"]
    assert C.runtime.held(vehicle, day) == draft and order in C.runtime.orders_in_drafts(day)
    assert draft in [d["draft_id"] for d in b.call("list_dispatch_drafts", {})["result"]["drafts"]]
    assert not b.call("cancel_dispatch_draft", {"draft_id": draft})["result"]["cancelled"]       # the agent can't undo a sign-off
    assert C.runtime.held(vehicle, day) == draft
    assert not C.runtime.decide(draft, "approve", "", "reviewer")
    assert C.runtime.decide(draft, "reject", "wrong truck", "reviewer")
    assert C.runtime.held(vehicle, day) is None and order not in C.runtime.orders_in_drafts(day)
    assert [d["decision"] for d in C.runtime.decisions(draft)] == ["approve", "reject"]


def live_chat(c, monkeypatch, script, msg="plan it"):
    script_model(monkeypatch, script)
    r = c.post("/api/chat", json={"company": "T01", "message": msg, "mode": "live", "team": False}).json()
    assert wait(r["run_id"])["status"] == "done"
    return r["run_id"]


def api_client(world, public=False):
    return TestClient(api_app.create_app(public=public, world=world, replay_pace=0))


def test_stop_ask_and_resume_through_the_api(env, monkeypatch):
    c = api_client(env)
    rid = live_chat(c, monkeypatch, [mock_tool_call("list_sites", {}), mock_tool_call("ask_person", ASK)], "Warangal load")
    waiting = c.get("/api/handoffs?company=T01").json()
    assert [w["run_id"] for w in waiting] == [rid] and waiting[0]["handoff"]["question"] == ASK["question"]
    assert "messages" not in c.get(f"/api/runs/{rid}").json() and c.get(f"/api/runs/{rid}").json()["stop"] == "needs_person"

    client = MockClient([mock_final("Okay, the first one.")])
    monkeypatch.setattr(muse, "client", lambda name="spark", **k: client)
    r = c.post(f"/api/runs/{rid}/resume", json={"reply": "Lakshmi Agencies", "model": "open"}).json()
    assert r["resumed_from"] == rid and wait(r["run_id"])["stop"] == "answered"
    sent = client.calls[0]["messages"]
    assert sent[-1] == {"role": "user", "content": "Lakshmi Agencies"} and any(m.get("tool_calls") for m in sent)     # kept the conversation
    done = c.get(f"/api/runs/{r['run_id']}").json()
    assert done["resumed_from"] == rid and done["reply"] == "Okay, the first one."
    assert c.get("/api/handoffs?company=T01").json() == []
    assert c.post(f"/api/runs/{rid}/resume", json={"reply": "again"}).json()["error"]["code"] == "ALREADY_RESUMED"
    assert c.post(f"/api/runs/{r['run_id']}/resume", json={"reply": "more"}).json()["error"]["code"] == "NOT_WAITING"


def test_a_crashed_resume_can_be_tried_again_and_another_visitor_cannot_touch_it(env, monkeypatch):
    c = api_client(env, public=True)
    rid = live_chat(c, monkeypatch, [mock_tool_call("list_sites", {}), mock_tool_call("ask_person", ASK)])
    assert api_client(env, public=True).post(f"/api/runs/{rid}/resume", json={"reply": "x"}).status_code == 404
    assert api_client(env, public=True).get("/api/handoffs?company=T01").json() == []
    monkeypatch.setattr("anubhav.service.runs.run_with", lambda *a, **k: 1 / 0)
    r = c.post(f"/api/runs/{rid}/resume", json={"reply": "x"}).json()
    assert wait(r["run_id"])["status"] == "error"
    assert checkpoints.get(rid, c.cookies[deps.COOKIE])["status"] == "open"


def test_sign_off_through_the_api_and_rejected_notes_reach_the_agent(env, monkeypatch):
    c = api_client(env)
    C = session.Workspace(world=env).company("T01")
    C.runtime.reset()
    order, vehicle, _ = one_draft(C)
    C.runtime.reset()
    args = {"order_ids": [order], "vehicle_id": vehicle}
    rid = live_chat(c, monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("Drafted it.")])
    draft = c.get(f"/api/runs/{rid}").json()["drafts"][0]
    decide = lambda **b: c.post(f"/api/dashboard/drafts/{draft}/decide?company=T01", json=b)

    assert decide(decision="reject").status_code == 422
    assert c.post("/api/dashboard/drafts/NOPE/decide?company=T01", json={"decision": "approve"}).status_code == 404
    assert decide(decision="approve").json()["status"] == "approved"
    assert decide(decision="approve").status_code == 409
    row = next(d for d in c.get("/api/dashboard/drafts?company=T01").json()["drafts"] if d["draft_id"] == draft)
    assert row["decisions"][0]["decided_by"] == "reviewer" and row["stops"]

    client = MockClient([mock_final("I will use another truck.")])
    monkeypatch.setattr(muse, "client", lambda name="spark", **k: client)
    out = decide(decision="reject", notes="This truck can't enter that lane").json()
    assert out["status"] == "rejected" and wait(out["revise_run_id"])["stop"] == "answered"
    assert "This truck can't enter that lane" in client.calls[0]["messages"][-1]["content"]
    assert c.get(f"/api/runs/{out['revise_run_id']}").json()["drafts"] == []     # the rejected one isn't carried on
    C.runtime.reset()


def test_approving_re_checks_the_plan_first(env, monkeypatch):
    C = session.Workspace(world=env).company("T01")
    C.runtime.reset()
    order, _, draft = one_draft(C)
    c = api_client(env)
    C.orders[order]["status"], was = "cancelled", C.orders[order]["status"]
    try:
        assert c.post(f"/api/dashboard/drafts/{draft}/decide?company=T01", json={"decision": "approve"}).status_code == 409
        assert C.runtime.draft(draft)["status"] == "draft"
    finally:
        C.orders[order]["status"] = was
        C.runtime.reset()


# ---------- setup check
def test_preflight_reports_without_spending_or_showing_keys(world, monkeypatch):
    monkeypatch.setenv(muse.KEYS["spark"], "sk-secret-value")
    assert preflight.check_model("spark", lambda k: [muse.DEFAULT_MODEL])[1]
    assert not preflight.check_model("spark", lambda k: ["something-else"])[1]
    boom = preflight.check_model("spark", lambda k: 1 / 0)
    assert not boom[1] and "ZeroDivisionError" in boom[2]
    monkeypatch.delenv(muse.KEYS["open"], raising=False)
    missing = preflight.check_model("open")
    assert not missing[1] and muse.KEYS["open"] in missing[2]
    rows = preflight.run(models=(), world=world)
    assert all(ok for name, ok, _ in rows if name != "live runs left today") and "sk-secret-value" not in str(rows)
    assert not dict((n, ok) for n, ok, _ in preflight.run(models=(), world=world, bundle=world / "none.jsonl"))["saved replays"]


def test_preflight_warns_when_credit_falls_into_the_demo_reserve(tmp_path):
    ledger = tmp_path / "l.md"
    ledger.write_text("| Meta Model API | 150.00 | ~110.0 | ~40.0 | x |\n| Baseten | 100.00 (+2M TPM) | ~64.7 | ~35.3 | y |\n", encoding="utf-8")
    meta, base = preflight.check_credits(ledger)
    assert not meta[1] and "~$0.00 free" in meta[2] and base[1] and "free" not in base[2]
    assert not preflight.check_credits(tmp_path / "none.md")[0][1]
    assert all(ok for _, ok, _ in preflight.check_credits())    # the real ledger today
