"""Every endpoint of the API (contracts/api.md) through FastAPI's test client, as a public-host visitor and as a local
user. Mock model only; no credits. Keys are removed so nothing can reach a real model."""

import json
import shutil
import subprocess

import jsonschema
import pytest
from fastapi.testclient import TestClient

from anubhav import muse, trace
from anubhav.api import app as api_app, deps
from anubhav.data import generate
from anubhav.data.config import ROOT
from anubhav.learning import newtools as nt
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.service import session, stream
from anubhav.service.session import SUGGESTIONS, Workspace

SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))
ROUTES = [("GET", "/api/health"), ("GET", "/api/session"), ("GET", "/api/companies"), ("GET", "/api/suggestions"),
          ("GET", "/api/dashboard/orders"), ("GET", "/api/dashboard/fleet"), ("GET", "/api/dashboard/drafts"), ("GET", "/api/dashboard/company"),
          ("GET", "/api/agents"), ("GET", "/api/agents/analyst"), ("GET", "/api/learning/lessons"), ("GET", "/api/tools"), ("GET", "/api/tools/candidates"),
          ("GET", "/api/harness"), ("GET", "/api/harness/problems"), ("GET", "/api/practice"), ("GET", "/api/packs"), ("GET", "/api/review/history"),
          ("GET", "/api/proof"), ("GET", "/api/ledger"), ("GET", "/api/logs/events"), ("GET", "/api/logs/runs"), ("GET", "/api/logs/tools"),
          ("GET", "/api/logs/models"), ("GET", "/api/logs/agents"), ("GET", "/api/proof/curve"), ("GET", "/api/proof/registry"), ("GET", "/api/logs/routing"), ("GET", "/api/learning/timeline"), ("GET", "/api/report/weekly")]
LOCKED = [("POST", "/api/learning/mine"), ("POST", "/api/harness/propose"), ("POST", "/api/harness/rollback"), ("POST", "/api/harness/h-001/probe"),
          ("POST", "/api/harness/h-001/decide"), ("POST", "/api/practice")]


@pytest.fixture(scope="module")
def source_world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def env(source_world, tmp_path, monkeypatch):
    for k in muse.KEYS.values():
        monkeypatch.delenv(k, raising=False)
    w = tmp_path / "w"
    shutil.copytree(source_world, w)
    d = tmp_path / "traces"
    d.mkdir()
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    session._harness.cache_clear()
    monkeypatch.setattr(session.harness_store, "__defaults__", (tmp_path / "harness.sqlite",))
    return w


def client(world, public=True):
    return TestClient(api_app.create_app(public=public, world=world, replay_pace=0), raise_server_exceptions=False)


def sse(text):
    """Parse a server-sent-event body into (event, id, data)."""
    out = []
    for block in text.strip().split("\n\n"):
        f = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        out.append((f["event"], f.get("id"), json.loads(f["data"])))
    return out


# ---------- every read opens, in both modes
@pytest.mark.parametrize("public", [True, False])
@pytest.mark.parametrize("method,path", ROUTES)
def test_every_read_endpoint_opens_without_keys(env, public, method, path):
    r = client(env, public).request(method, path)
    assert r.status_code == 200, r.text


def test_the_route_list_above_is_complete(env):
    paths = set(api_app.create_app(public=True, world=env).openapi()["paths"])
    assert len(paths) >= 40
    tested = {p for _, p in ROUTES + LOCKED}
    other = {"/api/session/reset-drafts", "/api/dashboard/drafts/{draft_id}/cancel", "/api/dashboard/company/profile", "/api/chat", "/api/chat/stream",
             "/api/runs/{run_id}", "/api/runs/{run_id}/feedback", "/api/learning/lessons/{lesson_id}/decide", "/api/tools/candidates/{key}/check",
             "/api/tools/{tool_id}/decide", "/api/tools/{tool_id}/retire", "/api/packs/publish", "/api/packs/revoke", "/api/review/run",
             "/api/dashboard/drafts/{draft_id}/decide", "/api/handoffs", "/api/runs/{run_id}/resume", "/api/compare", "/api/agents/{agent_id}", "/api/harness/{version_id}/probe", "/api/harness/{version_id}/decide", "/api/logs/runs/{run_id}", "/api/voice", "/api/learning/lessons/{lesson_id}/evidence",
             "/api/runs/{run_id}/steps", "/api/fresh/status", "/api/fresh/start", "/api/fresh/restore", "/api/fresh/mode", "/api/fresh/reset", "/api/fresh/set-aside", "/api/tools/health", "/api/tools/{tool_id}/repair", "/api/fresh/records", "/api/fresh/learn",
             "/api/data/tables", "/api/data/rows"}
    normal = {p.replace("/analyst", "/{agent_id}").replace("/h-001/", "/{version_id}/") for p in tested}
    assert paths <= normal | other, paths - normal - other


def test_errors_have_one_shape(env):
    c = client(env)
    for r, code in ((c.get("/api/dashboard/orders?company=NOPE"), "NOT_FOUND"), (c.get("/api/nope"), "NOT_FOUND"),
                    (c.post("/api/chat", json={"message": ""}), "BAD_ARGS"), (c.post("/api/chat", json={"message": "x", "spoof": 1}), "BAD_ARGS"),
                    (c.get("/api/runs/nope"), "NOT_FOUND")):
        assert r.json()["error"]["code"] == code and r.json()["error"]["message"]


def test_a_crash_never_shows_its_details(env, monkeypatch):
    monkeypatch.setattr(api_app.session, "WORLD", env)
    from anubhav.service import proof
    monkeypatch.setattr(proof, "results", lambda: 1 / 0)
    r = client(env).get("/api/proof")
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL" and "division" not in r.text


# ---------- the public host
@pytest.mark.parametrize("method,path", LOCKED)
def test_shared_and_paid_actions_are_refused_on_the_public_host(env, method, path):
    r = client(env).request(method, path, json={"approve": True} if "decide" in path else None)
    assert r.status_code == 403 and r.json()["error"]["code"] == "READ_ONLY_PUBLIC"


def test_session_says_live_is_off_without_keys_and_never_shows_a_key(env, monkeypatch):
    body = client(env).get("/api/session").json()
    assert body["public"] and body["default_mode"] == "replay" and body["default_team"]
    assert not body["models"]["Muse Spark 1.3"]["available"] and "Use Replay" in body["models"]["Muse Spark 1.3"]["reason"]
    monkeypatch.setenv(muse.KEYS["spark"], "sk-secret-value")
    assert "sk-secret-value" not in client(env).get("/api/session").text


def test_session_reports_live_runs_used_and_left_for_the_visit_and_the_day(voice_env, monkeypatch):
    world, _, _ = voice_env
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    c = client(world)
    before = c.get("/api/session").json()
    assert before["live_runs_used"] == 0 and before["live_runs_left"] == before["caps"]["per_session"]
    assert before["live_runs_left_today"] <= before["caps"]["per_day"]
    assert post_voice(c, wav_bytes()).status_code == 200            # a transcription counts as one live run
    after = c.get("/api/session").json()
    assert after["live_runs_used"] == 1 and after["live_runs_left"] == before["live_runs_left"] - 1
    assert after["live_runs_left_today"] == before["live_runs_left_today"] - 1


def test_a_bad_cookie_is_replaced_never_used_as_a_path(env):
    c = client(env)
    c.cookies.set(deps.COOKIE, "../../etc")
    r = c.get("/api/learning/lessons")
    assert r.status_code == 200 and deps.SID.fullmatch(r.cookies[deps.COOKIE])
    assert not (env.parent.parent / "etc.sqlite").exists()


def test_visitors_are_isolated(env):
    a, b = client(env), client(env)
    a.get("/api/session"), b.get("/api/session")
    assert a.cookies[deps.COOKIE] != b.cookies[deps.COOKIE]
    lid = next(l["lesson_id"] for l in a.get("/api/learning/lessons").json() if l["state"] in ("ACTIVE_ADVISORY", "ACTIVE_POLICY"))
    assert a.post(f"/api/learning/lessons/{lid}/decide", json={"decision": "retire", "why": "test"}).status_code == 200
    state = lambda c: next(l["state"] for l in c.get("/api/learning/lessons").json() if l["lesson_id"] == lid)
    assert state(a) == "RETIRED" and state(b) != "RETIRED"


# ---------- chat and stream
def test_replay_request_streams_valid_events_and_ends(env):
    c = client(env)
    r = c.post("/api/chat", json={"message": SUGGESTIONS["New tool"], "use_lessons": False}).json()
    assert r["mode"] == "replay"
    s = c.get(f"/api/chat/stream?run_id={r['run_id']}")
    assert s.headers["content-type"].startswith("text/event-stream")
    got = sse(s.text)
    assert got[-1][0] == "end" and got[-1][2]["mode"] == "replay" and got[0][0] == "agent_start"
    for kind, seq, e in got[:-1]:
        jsonschema.validate(e, SCHEMA)
        assert kind == e["type"] and int(seq) == e["seq"]
    resumed = sse(c.get(f"/api/chat/stream?run_id={r['run_id']}", headers={"Last-Event-ID": "2"}).text)
    assert [int(x[1]) for x in resumed[:-1]] == [int(x[1]) for x in got[3:-1]]


def test_no_saved_run_says_so_with_suggestions(env):
    r = client(env).post("/api/chat", json={"message": "never asked", "use_lessons": False})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_REPLAY" and "New tool" in r.json()["error"]["suggestions"]


def test_live_without_a_key_falls_back_to_replay_and_says_why(env):
    r = client(env).post("/api/chat", json={"message": SUGGESTIONS["New tool"], "use_lessons": False, "mode": "live"}).json()
    assert r["mode"] == "replay" and "Live mode is off" in r["reason"]


def live_env(monkeypatch, script):
    monkeypatch.setenv(muse.KEYS[session.AGENT_MODEL], "test")
    monkeypatch.setattr(muse, "client", lambda name: MockClient(script))


def test_a_live_team_request_streams_handoff_and_is_saved(env, monkeypatch):
    live_env(monkeypatch, [mock_tool_call("delegate", {"agent": "analyst", "brief": "Count our sites in each town please."}),
                           mock_tool_call("list_sites", {}), mock_final("45"), mock_final("45 sites")])
    c = client(env)
    r = c.post("/api/chat", json={"message": "sites?", "mode": "live", "team": True}).json()
    assert r["mode"] == "live"
    got = sse(c.get(f"/api/chat/stream?run_id={r['run_id']}").text)
    types = [x[0] for x in got]
    assert "handoff" in types and types[-1] == "end" and got[-1][2]["stop"] == "answered"
    for kind, _, e in got[:-1]:
        jsonschema.validate(e, SCHEMA)
    saved = c.get(f"/api/runs/{r['run_id']}").json()
    assert saved["mode"] == "team" and saved["children"][0]["agent_id"] == "analyst" and saved["visitor"]
    assert c.get("/api/logs/runs").json()[0]["agents"] == ["planner", "analyst"]
    assert c.get("/api/session").json()["live_runs_left"] == session.LIVE_RUNS_PER_SESSION - 1


def test_another_visitor_cant_read_or_stream_a_live_run(env, monkeypatch):
    live_env(monkeypatch, [mock_final("hello")])
    a, b = client(env), client(env)
    run_id = a.post("/api/chat", json={"message": "hi", "mode": "live", "use_lessons": False}).json()["run_id"]
    list(stream.follow(run_id))
    b.get("/api/session")
    assert b.get(f"/api/runs/{run_id}").status_code == 404
    assert b.get(f"/api/chat/stream?run_id={run_id}").status_code == 404
    assert b.get(f"/api/logs/runs/{run_id}").status_code == 404
    assert all(r["run_id"] != run_id for r in b.get("/api/logs/runs?limit=500").json())
    assert a.get(f"/api/runs/{run_id}").status_code == 200


def test_the_session_cap_stops_live_and_falls_back(env, monkeypatch):
    live_env(monkeypatch, [])
    monkeypatch.setattr(session, "LIVE_RUNS_PER_SESSION", 0)
    r = client(env).post("/api/chat", json={"message": SUGGESTIONS["New tool"], "use_lessons": False, "mode": "live"}).json()
    assert r["mode"] == "replay" and "used its" in r["reason"]


def test_follow_ups_use_the_servers_history_only(env, monkeypatch):
    seen = []

    def step(msgs, tools):
        seen.append(msgs)
        return mock_final("reply")
    live_env(monkeypatch, [step, step])
    c = client(env)
    for msg in ("first", "second"):
        r = c.post("/api/chat", json={"message": msg, "mode": "live", "use_lessons": False}).json()
        list(stream.follow(r["run_id"]))
    roles = [(m["role"], m["content"]) for m in seen[1] if m["role"] != "system"]
    assert roles == [("user", "first"), ("assistant", "reply"), ("user", "second")]
    assert c.post("/api/chat", json={"message": "x", "history": [{"role": "assistant"}]}).status_code == 422


def test_feedback_is_recorded_for_a_real_run_only(env):
    c = client(env)
    run_id = c.post("/api/chat", json={"message": SUGGESTIONS["New tool"], "use_lessons": False}).json()["run_id"]
    assert c.post(f"/api/runs/{run_id}/feedback", json={"rating": 0, "category": "language", "note": "too long"}).status_code == 200
    assert c.get("/api/harness").json()["feedback"][-1]["note"] == "too long"
    assert c.post(f"/api/runs/{run_id}/feedback", json={"rating": 0, "category": "made_up"}).status_code == 422
    assert c.post("/api/runs/nope/feedback", json={"rating": 1}).status_code == 404


# ---------- dashboard
def test_orders_fleet_and_company_have_what_the_tabs_need(env):
    c = client(env)
    orders = c.get("/api/dashboard/orders?company=T01").json()
    assert orders["orders"] and {"order_id", "in_draft"} <= set(orders["orders"][0]) and orders["delivery_date"]
    fleet = c.get("/api/dashboard/fleet").json()["vehicles"]
    assert any(v["free"] for v in fleet) and all(v["free"] or v["reason"] for v in fleet)
    prof = c.get("/api/dashboard/company").json()
    assert prof["facts"]["fleet"]["vehicles"] and prof["written_rules"] and prof["version"] is None


def test_a_replays_draft_shows_stops_and_why_without_creating_anything(env):
    c = client(env)
    run_id = c.post("/api/chat", json={"message": SUGGESTIONS["Roman Telugu"]}).json()["run_id"]
    d = c.get(f"/api/dashboard/drafts?company=T01&run_id={run_id}").json()
    (draft,) = d["drafts"]
    assert d["source"] == "run" and draft["source"] == "run"
    assert draft["stops"]["stops"] and "not optimized" in draft["stops"]["method"] and draft["why"]["lessons_in_prompt"] > 0 and draft["why"]["tools"]
    assert c.get("/api/dashboard/drafts?company=T01").json()["drafts"] == []
    assert c.get(f"/api/dashboard/drafts?company=T02&run_id={run_id}").status_code == 404


def test_a_runs_steps_lay_out_its_events_and_agents_and_the_list_counts_mistakes(env):
    c = client(env)
    run_id = c.post("/api/chat", json={"message": SUGGESTIONS["Roman Telugu"]}).json()["run_id"]
    v = c.get(f"/api/runs/{run_id}/steps").json()
    assert v["events"][0]["type"] == "agent_start" and v["events"][-1]["type"] == "agent_done"
    (planner,) = v["agents"]
    assert planner["agent"] == "planner" and planner["tool_calls"] == sum(e["type"] == "tool_call" for e in v["events"]) and planner["own_cost_usd"] == planner["cost_usd"]
    assert v["fixes"] == [] or all(f["failed"]["step"] < f["fixed"]["step"] for f in v["fixes"])
    row = next(r for r in c.get("/api/logs/runs?company=T01").json() if r["run_id"] == run_id)
    assert {"mistakes", "fixed"} <= set(row) and row["fixed"] <= row["mistakes"]
    assert c.get("/api/runs/NOPE/steps").status_code == 404


def test_a_live_draft_appears_with_why_and_can_be_cancelled(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    orders = [o for o in c.get("/api/dashboard/orders").json()["orders"]]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    args = next(({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]}) for o in orders for v in free if o["kg"] <= v["payload_kg"])
    live_env(monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("draft")])
    run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    drafts = c.get("/api/dashboard/drafts").json()["drafts"]
    if not drafts:          # the validator can refuse the first pairing; that is its job, not this test's
        pytest.skip("validator refused the picked pair")
    (d,) = drafts
    assert d["why"]["run_id"] == run["run_id"] and d["stops"]["stops"]
    by_run = c.get(f"/api/dashboard/drafts?run_id={run['run_id']}").json()   # the chat asks by run: a live draft is the real one
    assert by_run["source"] == "live" and by_run["drafts"][0]["status"] == "draft" and by_run["drafts"][0]["source"] == "live"
    assert c.get("/api/dashboard/orders").json()["orders"][0] is not None
    assert c.post(f"/api/dashboard/drafts/{d['draft_id']}/cancel").status_code == 200
    assert c.post("/api/dashboard/drafts/DR-NONE/cancel").status_code == 404
    assert c.post("/api/session/reset-drafts").status_code == 200


def test_owner_profile_saves_a_new_version_and_refuses_unknown_fields(env):
    c = client(env)
    field = next(iter(c.get("/api/dashboard/company").json()["owner_fields"]))
    r = c.put("/api/dashboard/company/profile", json={"owner": {field: "We deliver at night"}}).json()
    assert r["version"] == 1 and r["agent_reads"] and "We deliver at night" in r["agent_reads"]
    assert c.put("/api/dashboard/company/profile", json={"owner": {"nope": "x"}}).status_code == 422


# ---------- lessons
def test_lesson_decisions_follow_the_stores_rules(env):
    c = client(env)
    c.get("/api/session")
    lessons = c.get("/api/learning/lessons").json()
    assert lessons[0]["what"] and "events" in lessons[0]
    active = next(l for l in lessons if l["state"] in ("ACTIVE_ADVISORY", "ACTIVE_POLICY"))
    url = f"/api/learning/lessons/{active['lesson_id']}/decide"
    assert c.post(url, json={"decision": "approve"}).json()["error"]["code"] == "CONFLICT"       # already active
    assert c.post(url, json={"decision": "retire"}).json()["error"]["code"] == "BAD_ARGS"       # needs a reason
    assert c.post(url, json={"decision": "retire", "why": "closed"}).json()["state"] == "RETIRED"
    assert c.post(url, json={"decision": "rollback"}).json()["state"] == active["state"]
    assert c.post("/api/learning/lessons/L-NOPE/decide", json={"decision": "rollback"}).status_code == 404


# ---------- new tools
def test_the_hosted_new_tool_story_works_through_the_api(env):
    c = client(env)
    groups = c.get("/api/tools/candidates").json()
    g = next(x for x in groups if x["reached_threshold"])
    assert len(g["requests"]) >= nt.MIN_USES and g["threshold"] == 3
    t = c.post(f"/api/tools/candidates/{g['key']}/check", json={}).json()
    assert t["status"] == "candidate" and t["checks"]["pass"]
    assert g["key"] not in {x["key"] for x in c.get("/api/tools/candidates").json()}
    assert c.post(f"/api/tools/{t['tool_id']}/decide", json={"approve": True}).json()["status"] == "active"
    assert [x["tool_id"] for x in c.get("/api/tools?status=active").json()] == [t["tool_id"]]
    after = c.post("/api/chat", json={"message": SUGGESTIONS["New tool"], "use_lessons": False}).json()
    assert c.get(f"/api/runs/{after['run_id']}").json()["tool_calls"] == 1
    assert c.post(f"/api/tools/{t['tool_id']}/retire").json()["status"] == "retired"
    other = client(env)
    assert other.get("/api/tools?status=active").json() == []                                    # another visitor is untouched


def test_a_tool_whose_checks_failed_cant_be_approved_and_a_bad_name_is_refused(env):
    c = client(env)
    g = next(x for x in c.get("/api/tools/candidates").json() if x["reached_threshold"])
    town = g["params"][0]["value"]
    bad = c.post(f"/api/tools/candidates/{g['key']}/check", json={"name": f"stops_{town.lower()}"})
    assert bad.status_code == 409 and "mentions" in bad.json()["error"]["message"]
    assert c.post("/api/tools/NT-NONE/decide", json={"approve": True}).status_code == 404
    ws = Workspace(c.cookies[deps.COOKIE], True, {}, env)
    t = c.post(f"/api/tools/candidates/{g['key']}/check", json={}).json()
    import sqlite3
    with sqlite3.connect(ws.store_path()) as con:
        con.execute("update tools set checks = ? where tool_id = ?", (json.dumps({"pass": False, "reasons": ["x"]}), t["tool_id"]))
    con.close()
    assert c.post(f"/api/tools/{t['tool_id']}/decide", json={"approve": True}).status_code == 403


# ---------- sharing, review, logs, proof
def test_publish_accept_and_revoke_a_pack_with_no_leaks(env):
    c = client(env)
    done = c.post("/api/packs/publish", json={"sources": ["T01"], "target": "TNEW"}).json()
    assert done[0]["items"] > 0 and done[0]["leaks"] == [] and c.get("/api/packs").json()["received"]
    assert c.post("/api/packs/revoke").json()["revoked"] and c.get("/api/packs").json()["received"] == []
    assert c.post("/api/packs/publish", json={"sources": ["NOPE"]}).status_code == 404


def test_nightly_review_is_free_on_the_public_host_and_recorded(env, monkeypatch):
    live_env(monkeypatch, [])                    # keys present, but a visitor's review must not spend
    c = client(env)
    rep = c.post("/api/review/run").json()
    assert rep["facts"]["route"].startswith(("skipped", "no corrections")) and "missing_tools" in rep
    assert c.get("/api/session").json()["live_runs_left"] == session.LIVE_RUNS_PER_SESSION
    assert c.get("/api/review/history").json()[0]["report"]["runs"] == rep["runs"]


def test_logs_ledger_and_tool_tracking_read_the_runs(env):
    c = client(env)
    runs = c.get("/api/logs/runs?company=T01").json()
    r = next(x for x in runs if x["drafts"])
    assert r["agents"] == ["planner"] and r["mode"] == "single"
    detail = c.get(f"/api/logs/runs/{r['run_id']}").json()
    assert {x["kind"] for x in detail["timeline"]} >= {"act", "observe", "check"} and "raw" not in detail["timeline"][0]
    usage = c.get("/api/logs/tools").json()
    assert usage["usage"][0]["calls"] > 0 and usage["missing"] == []
    ledger = c.get("/api/ledger?company=T01&type=draft_created").json()
    assert ledger and {e["type"] for e in ledger} == {"draft_created"}
    assert all("raw" not in e for e in c.get("/api/logs/events?company=T01").json())
    assert c.get("/api/logs/models").json()[0]["model"] == "Muse Spark Open"
    assert "Lesson" in c.get("/api/report/weekly").json()["markdown"] or c.get("/api/report/weekly").json()["markdown"]


def test_proof_says_what_each_result_measured(env):
    results = {x["id"]: x for x in client(env).get("/api/proof").json()}
    assert {"EXP-011", "EXP-011R", "EXP-012", "EXP-012b", "EXP-009", "EXP-009b"} <= set(results)
    assert all(x["measured_on"] for x in results.values()) and results["EXP-011R"]["replicated"]["lessons"]
    assert "threshold of 2" in results["EXP-012b"]["measured_on"]
    assert results["EXP-013"]["decision"]["team_becomes_default"] and not results["EXP-013"]["decision"]["R4_met"]


def test_agents_roster_and_detail(env):
    c = client(env)
    roster = {a["agent"]: a for a in c.get("/api/agents").json()}
    assert roster["planner"]["voice"] and roster["tool_forge"]["status"] == "active" and roster["lesson_miner"]["status"] == "active"
    assert "{company}" in c.get("/api/agents/analyst").json()["instructions"] and c.get("/api/agents/nope").status_code == 404


def test_the_api_never_loads_streamlit():
    import subprocess
    import sys
    code = "import sys, anubhav.api.routes; sys.exit('streamlit' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


# ---------- voice (transcription is mocked: no credits)
def wav_bytes(seconds=0.2):
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def post_voice(c, body):
    return c.post("/api/voice", content=body, headers={"Content-Type": "audio/wav"})


@pytest.fixture
def voice_env(env, monkeypatch):
    from anubhav.api import routes
    calls = []
    monkeypatch.setattr(routes, "transcribe", lambda p, kw: calls.append(kw) or {"transcript": "repu jangaon load", "audio_ms": 3200, "cost_usd": 0.0004})
    return env, calls, routes


def test_session_says_why_voice_is_off(voice_env):
    world, _, _ = voice_env
    v = client(world).get("/api/session").json()["voice"]
    assert v["available"] is False and muse.KEYS["spark"] in v["reason"] and "Replay" not in v["reason"] and v["reason"].startswith("Voice is off here")


def test_voice_is_refused_without_a_key(voice_env):
    world, calls, _ = voice_env
    r = post_voice(client(world), wav_bytes())
    assert r.status_code == 403 and r.json()["error"]["code"] == "LIVE_OFF" and calls == []


def test_voice_returns_transcript_and_meta(voice_env, monkeypatch):
    world, calls, _ = voice_env
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    c = client(world)
    assert c.get("/api/session").json()["voice"]["available"] is True
    r = post_voice(c, wav_bytes())
    assert r.status_code == 200 and r.json() == {"transcript": "repu jangaon load", "audio_ms": 3200, "cost_usd": 0.0004}
    assert "Warangal" in calls[0]       # town names go to the service as hints


@pytest.mark.parametrize("body,status,code", [
    pytest.param(b"", 400, "EMPTY_AUDIO", id="empty"),
    pytest.param(b"not a wav file", 415, "NOT_WAV", id="not-wav"),
    pytest.param(b"RIFF" + b"\x00" * (2 * 1024 * 1024 + 1), 413, "AUDIO_TOO_LARGE", id="too-large"),
])
def test_bad_audio_is_rejected(voice_env, monkeypatch, body, status, code):
    world, calls, _ = voice_env
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    r = post_voice(client(world), body)
    assert r.status_code == status and r.json()["error"]["code"] == code and calls == []


def test_silent_recording_gives_no_speech(voice_env, monkeypatch):
    world, _, routes = voice_env
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    monkeypatch.setattr(routes, "transcribe", lambda p, kw: {"transcript": "  ", "audio_ms": 1000, "cost_usd": 0.0001})
    r = post_voice(client(world), wav_bytes())
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_SPEECH"


def test_transcription_failure_is_a_502_and_the_session_is_still_usable(voice_env, monkeypatch):
    world, _, routes = voice_env
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    def boom(p, kw):
        raise ConnectionError("down")
    monkeypatch.setattr(routes, "transcribe", boom)
    c = client(world)
    r = post_voice(c, wav_bytes())
    assert r.status_code == 502 and r.json()["error"]["code"] == "TRANSCRIBE_FAILED"
    assert c.get("/api/health").status_code == 200


# ---------- evidence behind a lesson, and the experiment registry (build sprint 2; no model calls)
def evidence(c, lid, company="T01"):
    return c.get(f"/api/learning/lessons/{lid}/evidence", params={"company": company})


def lesson_of(c, kind, company="T01"):
    return next(l for l in c.get("/api/learning/lessons", params={"company": company}).json() if l["kind"] == kind)


def test_a_gate_lesson_shows_every_trip_to_its_site_as_the_gate_saw_them(env):
    c = client(env)
    lesson = lesson_of(c, "site_access")
    e = evidence(c, lesson["lesson_id"]).json()
    limit = lesson["params"]["max_length_ft"]
    assert e["kind"] == "trips" and e["site"]["site_id"] == lesson["params"]["site_id"] and e["limit"]["max_length_ft"] == limit
    refused = [r for r in e["rows"] if r["status"] == "returned"]
    assert refused and all(r["length_ft"] > limit for r in refused)                 # every refusal was a long truck
    assert all(r["length_ft"] <= limit for r in e["rows"] if r["status"] != "returned")
    assert lesson["gate"]["support"] == len([r for r in refused if r["status_seen"] == "could_not_enter"])
    assert [r["date"] for r in e["rows"]] == sorted(r["date"] for r in e["rows"])


def test_a_closure_shows_its_delays_by_week_and_none_after_it_ended(env):
    c = client(env)
    lesson = lesson_of(c, "closure")
    e = evidence(c, lesson["lesson_id"]).json()
    assert e["kind"] == "closure" and e["place"] == lesson["params"]["town"]
    assert sum(w["delays"] for w in e["weeks"]) == e["delays"] >= 3
    end = e["window"]["to"]
    assert all(w["delays"] == 0 for w in e["weeks"] if w["week"] > end)            # the road reopened: no delays after
    assert e["notes"] and [n["ts"] for n in e["notes"]] == sorted(n["ts"] for n in e["notes"])


def test_a_shared_lesson_never_shows_the_other_companys_records(env):
    c = client(env)
    shared = next(l for l in c.get("/api/learning/lessons", params={"company": "TNEW"}).json() if str(l["source"]).startswith("pack:"))
    e = evidence(c, shared["lesson_id"], "TNEW").json()
    assert e["kind"] == "imported" and "rows" not in e and "notes" not in e


def test_evidence_for_other_kinds_or_wrong_lessons(env):
    c = client(env)
    assert evidence(c, lesson_of(c, "alias")["lesson_id"]).json()["kind"] == "none"
    assert evidence(c, "L-NOPE").status_code == 404
    t01 = lesson_of(c, "site_access")["lesson_id"]
    assert evidence(c, t01, "T02").status_code == 404                               # a lesson is read through its own company only


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)


def test_the_experiment_registry_points_at_real_files_and_commits():
    reg = client_free_registry()
    rows = reg["experiments"]
    assert len(rows) == 21 and len({r["id"] for r in rows}) == 21
    assert {r["verdict"] for r in rows} <= {"met", "not_met", "finding", "not_run"}
    for r in rows:
        if r["result"]:
            assert (ROOT / r["result"]["file"]).exists(), r["id"]
        assert (r["custody"] == "not_run") == (r["result"] is None)
    if _git("rev-parse", "--is-shallow-repository").stdout.strip() != "false":
        pytest.skip("shallow clone: commit history not available")
    stamp = lambda h: int(_git("show", "-s", "--format=%ct", h).stdout.strip())
    for r in rows:
        assert _git("cat-file", "-e", f"{r['plan']['commit']}^{{commit}}").returncode == 0, r["id"]
        if r["result"]:
            assert _git("cat-file", "-e", f"{r['result']['commit']}^{{commit}}").returncode == 0, r["id"]
            if r["custody"] == "plan_first":
                assert stamp(r["plan"]["commit"]) < stamp(r["result"]["commit"]), r["id"]
            else:
                assert r["plan"]["commit"] == r["result"]["commit"], r["id"]


def test_the_registry_keeps_each_bar_and_the_proof_route_gives_per_company_totals(env):
    reg = client_free_registry()["experiments"]
    by = {r["id"]: r for r in reg}
    assert by["EXP-009b"]["bar"]["precision"] == 0.85 and by["EXP-008"]["verdict"] == "not_met"   # the mining bar was missed (0.73)
    assert by["EXP-015"]["verdict"] == "met" and by["EXP-014"]["verdict"] == "not_met" and by["EXP-016"]["verdict"] == "not_met"
    proof = {x["id"]: x for x in client(env).get("/api/proof").json()}
    assert "spark-1.3" in proof["EXP-015"]["model"] and proof["EXP-015"]["replicated"] == {"lessons": True, "transfer": True}
    assert client(env).get("/api/proof/curve").json()["measured"] is True
    r11 = next(x for x in client(env).get("/api/proof").json() if x["id"] == "EXP-011R")
    assert r11["summary"] and all(k.split(":")[0] in {"T01", "T02", "TNEW"} for k in r11["summary"]) and r11["runs"] > 0


def client_free_registry():
    from anubhav.service import proof
    return proof.registry()


def test_proof_adds_open_weights_and_demo_world_mining(env):
    entries = {e["id"]: e for e in client(env).get("/api/proof").json()}
    ow = entries["EXP-004"]["arms"]
    assert {a["tools"] for a in ow} == {8, 40}
    assert all("muse-spark-open" in a["spark_open"]["model"] and a["spark_open"]["runs"] == 96 for a in ow)
    m = entries["EXP-008"]
    assert len(m["repeats"]) == 2 and 0 < m["pooled"]["precision"] <= 1 and m["pooled"]["traps_admitted"] == 0


# ---------- start from nothing (final demo plan, Nov 3)
def test_start_fresh_empties_only_this_visitors_lessons_and_restore_brings_them_back(env):
    c, other = client(env), client(env)
    before = c.get("/api/fresh/status?company=T01").json()
    assert before["lessons"] > 0 and before["fresh"] is False and before["agent_versions"]["planner"] >= 1
    after = c.post("/api/fresh/start?company=T01").json()
    assert after == {**after, "fresh": True, "lessons": 0, "tools": 0}
    assert c.get("/api/learning/lessons?company=T01").json() == []
    assert other.get("/api/fresh/status?company=T01").json()["lessons"] > 0          # another visitor keeps theirs
    back = c.post("/api/fresh/restore?company=T01").json()
    assert back["lessons"] == before["lessons"] and back["fresh"] is False


def test_the_records_stage_counts_what_the_miner_reads_without_a_model(env):
    r = client(env).get("/api/fresh/records?company=T01").json()
    assert r["stops"] > 0 and r["drivers_notes"] > 0 and r["sites"] > 0 and r["from"] < r["to"]


def test_learning_needs_live_mode_and_runs_once_per_visit_when_hosted(env, monkeypatch):
    from anubhav.service import fresh
    c = client(env)
    c.post("/api/fresh/start?company=T01")
    assert c.post("/api/fresh/learn?company=T01").json()["error"]["code"] == "NO_KEY"   # no key: nothing spent
    monkeypatch.setenv(muse.KEYS["spark"], "test")
    monkeypatch.setattr(muse, "client", lambda name: MockClient([]))
    prop = {"kind": "site_access", "params": {"site_id": "C0003", "max_length_ft": 22}, "claim": "C0003 max 22 ft", "evidence": "returns"}
    monkeypatch.setattr(fresh.miner, "mine", lambda client, C, d: ([prop], {"model": "mock", "cost_usd": 0.01, "latency_s": 1}))
    r = c.post("/api/fresh/learn?company=T01").json()
    assert len(r["lessons"]) == 1 and r["lessons"][0]["display"] and r["lessons"][0]["reason"]
    assert c.get("/api/fresh/status?company=T01").json()["mines_left"] == 0
    again = c.post("/api/fresh/learn?company=T01").json()
    assert again["error"]["code"] == "CAP_REACHED"
    assert c.get("/api/session").json()["live_runs_used"] == 1                       # mining counted as one live run


def test_lessons_carry_a_display_text_for_people_and_the_agents_text_is_unchanged(env):
    rows = client(env).get("/api/learning/lessons?company=T01").json()
    gate = next(l for l in rows if l["kind"] == "site_access")
    assert "gets in" in gate["display"] and "cannot enter" in gate["what"]        # the agent keeps the measured wording


def test_on_a_public_host_rejecting_never_starts_a_live_revise(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    args = next(({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]}) for o in orders for v in free if o["kg"] <= v["payload_kg"])
    live_env(monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("draft")])
    run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    drafts = c.get("/api/dashboard/drafts").json()["drafts"]
    if not drafts:
        pytest.skip("validator refused the picked pair")
    used = c.get("/api/session").json()["live_runs_used"]
    out = c.post(f"/api/dashboard/drafts/{drafts[0]['draft_id']}/decide", json={"decision": "reject", "notes": "too long for the gate", "revise": True}).json()
    assert out["status"] == "rejected" and out["revise_run_id"] is None and "local run" in out["reason"]
    assert c.get("/api/session").json()["live_runs_used"] == used          # nothing spent


def test_asking_again_sets_the_first_draft_aside_so_the_order_is_free(env, monkeypatch):
    """S0's "Ask again": the first live draft holds the order, so it is cancelled first (kept in the audit)."""
    c = client(env)
    c.get("/api/session")
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    args = next(({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]}) for o in orders for v in free if o["kg"] <= v["payload_kg"])
    live_env(monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("draft")])
    run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    drafts = c.get("/api/dashboard/drafts").json()["drafts"]
    if not drafts:
        pytest.skip("validator refused the picked pair")
    out = c.post("/api/fresh/set-aside").json()
    assert out["cancelled"] == [drafts[0]["draft_id"]]
    assert c.post("/api/fresh/set-aside").json()["cancelled"] == []          # nothing left open
    other = client(env)
    other.get("/api/session")
    assert other.post("/api/fresh/set-aside").json()["cancelled"] == []     # another visitor's drafts are theirs


def test_without_the_cookie_the_visitor_header_keeps_the_same_workspace(env):
    """In the Hugging Face Space page the app is in a cross-site iframe and the cookie is dropped; the header carries it."""
    c = client(env)
    sid = c.get("/api/session").headers["X-Anubhav-Visitor"]
    c.post("/api/fresh/start?company=T01")
    c.cookies.clear()
    same = c.get("/api/fresh/status?company=T01", headers={"X-Anubhav-Visitor": sid})
    assert same.json()["fresh"] is True and same.headers["X-Anubhav-Visitor"] == sid
    assert c.get(f"/api/fresh/status?company=T01&visitor={sid}").json()["fresh"] is True     # the event stream's way
    c.cookies.clear()
    other = c.get("/api/fresh/status?company=T01", headers={"X-Anubhav-Visitor": "not-an-id!"})
    assert other.json()["fresh"] is False and other.headers["X-Anubhav-Visitor"] != sid


def test_on_the_hosted_demo_a_new_visitor_starts_from_zero_and_can_switch_to_the_recorded_lessons(env):
    c = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    c.get("/api/session")
    for cid in ("T01", "TNEW"):
        s = c.get(f"/api/fresh/status?company={cid}").json()
        assert s["fresh"] is True and s["lessons"] == 0 and s["tools"] == 0
    assert c.get("/api/learning/lessons?company=T01").json() == []
    back = c.post("/api/fresh/restore?company=T01").json()
    assert back["fresh"] is False and back["lessons"] > 0
    again = c.post("/api/fresh/start?company=T01").json()
    assert again["fresh"] is True and again["lessons"] == 0
    assert client(env).get("/api/fresh/status?company=T01").json()["fresh"] is False     # without the flag: recorded lessons


def test_session_names_the_default_model_and_each_models_key(env):
    s = client(env).get("/api/session").json()
    assert s["default_model"] == "spark"
    assert s["models"]["Muse Spark 1.3"]["key"] == "spark" and s["models"]["Muse Spark Open"]["key"] == "open"


def test_learning_from_the_records_takes_the_chosen_model(env):
    c = client(env)
    c.get("/api/session")
    for m in ("spark", "open"):
        r = c.post(f"/api/fresh/learn?company=T01&model={m}")
        assert r.status_code == 409 and r.json()["error"]["code"] == "NO_KEY"       # no keys in tests: nothing is called
    assert c.post("/api/fresh/learn?company=T01&model=gpt").status_code == 422


def test_a_live_draft_says_which_run_and_model_made_it(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    args = next(({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]}) for o in orders for v in free if o["kg"] <= v["payload_kg"])
    live_env(monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("draft")])
    run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    drafts = c.get("/api/dashboard/drafts").json()["drafts"]
    if not drafts:
        pytest.skip("validator refused the picked pair")
    assert drafts[0]["run_id"] == run["run_id"] and drafts[0]["model"]
    one = c.get(f"/api/dashboard/drafts?run_id={run['run_id']}").json()["drafts"]
    assert one[0]["model"] == drafts[0]["model"]


def test_a_fresh_start_workspace_lists_only_its_own_runs_and_reset_empties_the_list(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    recorded = c.get("/api/logs/runs?company=T01").json()
    assert recorded, "the After learning workspace shows the recorded runs"
    assert all(r["recorded"] for r in recorded)
    c.post("/api/fresh/start?company=T01")
    assert c.get("/api/logs/runs?company=T01").json() == []
    assert all(t["runs"] == 0 for t in c.get("/api/logs/agents?company=T01").json())
    live_env(monkeypatch, [mock_final("Nothing to plan.")])
    run = c.post("/api/chat", json={"message": "anything to plan?", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    mine = c.get("/api/logs/runs?company=T01").json()
    assert [r["run_id"] for r in mine] == [run["run_id"]] and mine[0]["recorded"] is False
    assert c.get(f"/api/runs/{recorded[0]['run_id']}").status_code == 200        # a recorded run still opens by id
    import time
    time.sleep(1.1)                                                              # Reset counts from the next second
    c.post("/api/fresh/start?company=T01")
    assert c.get("/api/logs/runs?company=T01").json() == []
    c.post("/api/fresh/restore?company=T01")
    after = {r["run_id"] for r in c.get("/api/logs/runs?company=T01").json()}
    assert recorded[0]["run_id"] in after and run["run_id"] not in after       # Fresh start's runs stay in Fresh start


def test_agents_show_their_tools_and_skills_and_the_tool_routes_answer(env):
    c = client(env)
    c.get("/api/session")
    rows = {a["agent"]: a for a in c.get("/api/agents?company=T01").json()}
    assert "run_query" not in str(rows["analyst"]["tools"]) and rows["analyst"]["tools"]["actions"] == ["read"]
    assert {s["name"] for s in rows["tool_forge"]["skills"]} >= {"debug-sql", "repair-a-tool"}
    assert all(rows[a]["skills"] for a in ("planner", "analyst", "tool_forge", "lesson_miner"))
    assert c.post("/api/tools/health?company=T01").json() == []                     # no approved tools yet
    assert c.post("/api/tools/NT-T01-nope/repair?company=T01").status_code == 404


def _two_live_drafts(c, monkeypatch):
    """Two live runs, each drafting a different order on a different free truck. Returns the two run ids, or None."""
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    pairs, used = [], set()
    for o in sorted(orders, key=lambda o: o["kg"]):
        v = next((v for v in free if v["vehicle_id"] not in used and o["kg"] <= v["payload_kg"]), None)
        if v:
            pairs.append({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]})
            used.add(v["vehicle_id"])
        if len(pairs) == 2:
            break
    run_ids = []
    for args in pairs:
        live_env(monkeypatch, [mock_tool_call("create_dispatch_draft", args), mock_final("draft")])
        run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
        list(stream.follow(run["run_id"]))
        run_ids.append(run["run_id"])
    return run_ids if len(c.get("/api/dashboard/drafts").json()["drafts"]) == 2 else None


def test_the_workspace_drafts_list_keeps_every_draft_across_requests_newest_first(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    run_ids = _two_live_drafts(c, monkeypatch)
    if not run_ids:
        pytest.skip("validator refused a picked pair")
    ws = c.get("/api/dashboard/drafts").json()
    assert ws["source"] == "live"
    first, second = run_ids
    assert [d["run_id"] for d in ws["drafts"]] == [second, first]          # the newer ask did not replace the older draft
    for d in ws["drafts"]:
        assert d["status"] == "draft" and d["source"] == "live" and d["model"] and d["created_at"]
        assert d["sites"] and all(", " in s for s in d["sites"])              # "Name, Town", in stop order
    # A run's own view still returns only that run's draft.
    assert [d["run_id"] for d in c.get(f"/api/dashboard/drafts?run_id={first}").json()["drafts"]] == [first]


def test_decided_drafts_stay_in_the_workspace_list_with_their_status(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    if not _two_live_drafts(c, monkeypatch):
        pytest.skip("validator refused a picked pair")
    newer, older = c.get("/api/dashboard/drafts").json()["drafts"]
    r = c.post(f"/api/dashboard/drafts/{older['draft_id']}/decide", json={"decision": "reject", "notes": "wrong truck", "revise": False})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    a = c.post(f"/api/dashboard/drafts/{newer['draft_id']}/decide", json={"decision": "approve"})
    after = {d["draft_id"]: d for d in c.get("/api/dashboard/drafts").json()["drafts"]}
    assert set(after) == {newer["draft_id"], older["draft_id"]}
    assert after[older["draft_id"]]["status"] == "rejected" and after[older["draft_id"]]["decisions"][0]["notes"] == "wrong truck"
    assert after[older["draft_id"]]["stops"] is None and after[older["draft_id"]]["sites"]   # freed, but still says where it was going
    assert after[newer["draft_id"]]["status"] == ("approved" if a.status_code == 200 else "draft")
    rows = {o["order_id"]: o for o in c.get("/api/dashboard/orders").json()["orders"]}
    assert rows[older["orders"][0]]["in_draft"] is False                    # a rejected draft frees its order


# ---------- Fresh start shows only this workspace's own data (Nov 4)
def test_a_visitor_id_the_server_has_never_seen_starts_fresh_and_keeps_its_mode_across_a_restart(env):
    """After a restart the page still sends its old id. The server has no state for it: it must start fresh, not get
    the recorded lessons seeded into a new store with no "Fresh start" mark (the bug the owner saw)."""
    sid = "abcdef012345"
    h = {"X-Anubhav-Visitor": sid}
    app1 = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    s = app1.get("/api/fresh/status?company=T01", headers=h).json()
    assert s["fresh"] is True and s["lessons"] == 0
    assert app1.get("/api/learning/lessons?company=T01", headers=h).json() == []
    assert app1.get("/api/logs/runs?company=T01", headers=h).json() == []
    # a restart where the files survive: the same id keeps its Fresh start workspace
    app2 = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    s = app2.get("/api/fresh/status?company=T01", headers=h).json()
    assert s["fresh"] is True and s["lessons"] == 0
    assert app2.get("/api/logs/runs?company=T01", headers=h).json() == []
    assert app2.post("/api/fresh/restore?company=T01", headers=h).json()["lessons"] > 0
    app3 = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    s = app3.get("/api/fresh/status?company=T01", headers=h).json()
    assert s["fresh"] is False and s["lessons"] > 0                                  # After learning stays After learning


def test_compare_in_a_fresh_start_workspace_shows_only_its_own_before_and_after_pairs(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    req = SUGGESTIONS["English"]
    recorded = c.get("/api/compare", params={"company": "T01", "request": req}).json()
    c.post("/api/fresh/start?company=T01")
    mine = c.get("/api/compare", params={"company": "T01", "request": req}).json()
    assert mine["cold"] is None and mine["with_lessons"] is None and mine["with_learned_tools"] is None and mine["pairs"] == []
    assert c.get("/api/compare?company=T01").json()["pairs"] == []
    assert recorded["cold"] and recorded["with_lessons"] and recorded["pairs"] == []   # After learning: the recorded example, never an own pair
    orig = session.Workspace.broker_args            # stands in for one approved lesson, so no model or gate is needed
    monkeypatch.setattr(session.Workspace, "broker_args", lambda self, cid, use: (["Site X takes no long trucks."] if use else [], *orig(self, cid, use)[1:]))
    ask = "anything to plan for tomorrow?"
    live_env(monkeypatch, [mock_final("Nothing to plan.")])
    before = c.post("/api/chat", json={"message": ask, "mode": "live", "use_lessons": False}).json()
    list(stream.follow(before["run_id"]))
    assert c.get("/api/compare?company=T01").json()["pairs"] == []                  # no run with lessons yet
    live_env(monkeypatch, [mock_final("Still nothing to plan.")])
    after = c.post("/api/chat", json={"message": ask, "mode": "live", "use_lessons": True}).json()
    list(stream.follow(after["run_id"]))
    pairs = c.get("/api/compare?company=T01").json()["pairs"]
    assert len(pairs) == 1 and pairs[0]["request"] == ask
    p = pairs[0]
    assert p["before"]["run_id"] == before["run_id"] and p["before"]["lessons_in_prompt"] == 0
    assert p["after"]["run_id"] == after["run_id"] and p["after"]["lessons_in_prompt"] == 1
    assert p["after"]["model"] and p["after"]["saved_at"] and "tool_calls" in p["after"] and "cost_usd" in p["after"]
    other = client(env)                                                              # another visitor sees none of it
    other.get("/api/session")
    other.post("/api/fresh/start?company=T01")
    assert other.get("/api/compare?company=T01").json()["pairs"] == []


def test_a_fresh_start_workspace_counts_only_its_own_knowledge_and_timeline(env):
    c = client(env)
    c.get("/api/session")
    assert any(a["knowledge_items"] for a in c.get("/api/agents?company=T01").json())    # recorded lessons in After learning
    import time
    time.sleep(1.1)                       # the shared agent versions were just made; Fresh start counts from the next second
    c.post("/api/fresh/start?company=T01")
    assert all(a["knowledge_items"] == 0 for a in c.get("/api/agents?company=T01").json())
    assert c.get("/api/learning/timeline?company=T01").json() == []
    assert c.get("/api/review/history?company=T01").json() == []
    assert [e for e in c.get("/api/logs/events?company=T01").json() if e["stream"] in ("run", "lesson", "harness", "feedback")] == []
    assert c.get("/api/tools?company=T01").json() == [] and c.get("/api/tools/candidates?company=T01").json() == []


def test_drafts_made_by_the_several_drafts_tool_have_the_same_fields_as_any_other(env, monkeypatch):
    """Nov 4 bug: create_dispatch_drafts names its orders order_ids and keeps no date per draft, so the drafts panel got
    orders: null and the page went blank. Every draft now has orders, a delivery date and warnings, however it was made."""
    c = client(env)
    c.get("/api/session")
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    pairs, used = [], set()
    for o in orders:
        v = next((v for v in free if v["vehicle_id"] not in used and o["kg"] <= v["payload_kg"]), None)
        if v:
            used.add(v["vehicle_id"])
            pairs.append({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]})
        if len(pairs) == 2:
            break
    live_env(monkeypatch, [mock_tool_call("create_dispatch_drafts", {"assignments": pairs}), mock_final("two drafts")])
    run = c.post("/api/chat", json={"message": "plan both", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    for url in ("/api/dashboard/drafts", f"/api/dashboard/drafts?run_id={run['run_id']}"):
        ds = c.get(url).json()["drafts"]
        if not ds:
            pytest.skip("the validator refused the picked pairs")
        for d in ds:
            assert isinstance(d["orders"], list) and d["orders"], (url, d)
            assert d["delivery_date"] and isinstance(d["warnings"], list), (url, d)


# ---------- one shape per kind of object, whichever tool or record made it (the page reads these without guessing)
def _several_drafts_run():
    """A saved run whose drafts came from create_dispatch_drafts: orders named order_ids, one date for all, one refused."""
    return {"run_id": "r-shape", "request": "plan both", "reply": "two drafts", "trace": [
        {"type": "tool", "name": "create_dispatch_drafts", "arguments": {}, "ok": True, "result": {
            "delivery_date": "2026-11-05", "created": 1, "failed": 1, "results": [
                {"vehicle_id": "V-1", "order_ids": ["O-1", "O-2"], "ok": True, "draft_id": "DR-AAA111", "load": {"kg": 900, "sites": []}, "warnings": []},
                {"vehicle_id": "V-2", "order_ids": ["O-3"], "ok": False, "error": {"code": "OVERLOAD", "message": "too heavy"}}]}}]}


def test_a_draft_event_from_the_several_drafts_tool_names_its_orders():
    from anubhav import events
    from anubhav.service import views
    ev = events.from_run(_several_drafts_run())
    made = [e["payload"] for e in ev if e["type"] == "draft_created"]
    assert made == [{"draft_id": "DR-AAA111", "vehicle_id": "V-1", "orders": ["O-1", "O-2"], "load": {"kg": 900, "sites": []}}]
    assert [d["orders"] for d in views.drafts(_several_drafts_run())] == [["O-1", "O-2"]]
    assert views.drafts(_several_drafts_run())[0]["delivery_date"] == "2026-11-05"


def test_the_ledger_and_the_run_inspector_list_a_several_drafts_runs_orders(env, monkeypatch):
    c = client(env)
    c.get("/api/session")
    orders = c.get("/api/dashboard/orders").json()["orders"]
    free = sorted((v for v in c.get("/api/dashboard/fleet").json()["vehicles"] if v["free"]), key=lambda v: -v["payload_kg"])
    args = next(({"order_ids": [o["order_id"]], "vehicle_id": v["vehicle_id"]}) for o in orders for v in free if o["kg"] <= v["payload_kg"])
    live_env(monkeypatch, [mock_tool_call("create_dispatch_drafts", {"assignments": [args]}), mock_final("one draft")])
    run = c.post("/api/chat", json={"message": "plan it", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(run["run_id"]))
    steps = c.get(f"/api/runs/{run['run_id']}/steps").json()
    made = [e["payload"] for e in steps["events"] if e["type"] == "draft_created"]
    if not made:
        pytest.skip("validator refused the picked pair")
    assert made[0]["orders"] == args["order_ids"]
    led = [e for e in c.get("/api/ledger?company=T01&type=draft_created").json() if e["run_id"] == run["run_id"]]
    assert led and all(isinstance(e["payload"]["orders"], list) and e["payload"]["orders"] for e in led)


def test_a_run_with_an_empty_trace_still_lays_out_for_the_inspector():
    from anubhav.service import run_view
    v = run_view.run_view({"run_id": "r-empty", "request": "hello", "trace": []})
    assert v["events"] and v["fixes"] == [] and [a["agent"] for a in v["agents"]] == ["planner"]
    assert v["reply"] is None and v["cost_usd"] is None        # missing, not invented: the page shows its own fallback


def test_a_stored_tool_always_reads_with_every_check_field():
    row = {"tool_id": "T01-tool-abc12345", "name": "x", "params": None, "checks": None, "source": None}
    t = nt._row(row)
    assert t["checks"] == {"pass": False, "same_rows": [], "held_out": [], "reasons": []} and t["params"] == []
    only_health = dict(row, checks=json.dumps({"health": {"ok": False, "reasons": ["r"], "checked": "2026-11-04T10:00:00"}}))
    t = nt._row(only_health)
    assert t["checks"]["same_rows"] == [] and t["checks"]["health"]["ok"] is False and t["checks"]["pass"] is False
    full = dict(row, checks=json.dumps({"pass": True, "same_rows": [{"request": "q", "rows": 2, "same": True}], "held_out": [], "reasons": []}))
    assert nt._row(full)["checks"]["pass"] is True         # a real verdict is never overwritten by the defaults


def test_hosted_state_can_live_on_a_persistent_disk(tmp_path, monkeypatch):
    """Nov 4: free Spaces reset their disk on every redeploy. With ANUBHAV_STATE_DIR (the Space's persistent disk),
    visitors' workspaces and spend counters are written there; when it can't be written, nothing breaks."""
    from anubhav.data import config
    from anubhav.service import session as sess
    monkeypatch.setenv("ANUBHAV_STATE_DIR", str(tmp_path / "disk"))
    assert config._state_dir() == tmp_path / "disk"
    blocked = tmp_path / "file"
    blocked.write_text("x")
    monkeypatch.setenv("ANUBHAV_STATE_DIR", str(blocked / "sub"))
    assert config._state_dir() is None                              # not writable: state stays where it was
    monkeypatch.setattr(sess, "STATE", tmp_path / "disk")
    ws = sess.Workspace("abc123def456", True, {}, tmp_path / "worlds" / "w1")
    assert ws.store_path() == tmp_path / "disk" / "worlds" / "w1" / "learning" / "sessions" / "abc123def456.sqlite"
    assert ws._spend_file().parent == tmp_path / "disk" / "worlds" / "w1" / "runtime"
    monkeypatch.setattr(sess, "STATE", None)
    assert sess.Workspace("abc123def456", True, {}, tmp_path / "worlds" / "w1").store_path().parent == tmp_path / "worlds" / "w1" / "learning" / "sessions"


# ---------- the Data tab: the company's records, as the agents query them
def test_data_tables_lists_the_canonical_tables_first_the_ones_judges_want(env):
    c = client(env)
    r = c.get("/api/data/tables?company=T01")
    assert r.status_code == 200, r.text
    ts = r.json()["tables"]
    names = [t["table"] for t in ts]
    assert names[:3] == ["orders", "order_items", "shipments"]
    assert {"trip_outcomes", "vehicles", "sites", "driver_notes", "planner_messages", "products"} <= set(names)
    orders = ts[0]
    assert orders["title"] == "Orders" and orders["rows"] > 100 and orders["date_column"] == "delivery_date"
    assert orders["date_min"] <= orders["date_max"]
    assert next(t for t in ts if t["table"] == "vehicles")["date_column"] is None     # expiry dates are not a record's date
    assert c.get("/api/data/tables?company=NOPE").status_code == 404


def test_data_rows_page_by_page(env):
    c = client(env)
    total = next(t["rows"] for t in c.get("/api/data/tables").json()["tables"] if t["table"] == "orders")
    a = c.get("/api/data/rows?company=T01&table=orders&limit=50").json()
    assert a["total"] == total and len(a["rows"]) == 50 and a["offset"] == 0 and a["next_offset"] == 50
    assert [col["name"] for col in a["columns"]][:2] == ["order_id", "site_id"]
    b = c.get("/api/data/rows?company=T01&table=orders&offset=50&limit=50").json()
    assert b["offset"] == 50 and not {r[0] for r in a["rows"]} & {r[0] for r in b["rows"]}
    last = c.get(f"/api/data/rows?company=T01&table=orders&offset={total - 3}").json()
    assert len(last["rows"]) == 3 and last["next_offset"] is None
    notes = c.get("/api/data/rows?table=driver_notes&limit=5").json()
    assert next(col for col in notes["columns"] if col["name"] == "text")["free_text"] is True


def test_data_rows_date_filter(env):
    c = client(env)
    meta = next(t for t in c.get("/api/data/tables").json()["tables"] if t["table"] == "orders")
    day = meta["date_max"]
    r = c.get(f"/api/data/rows?table=orders&date_from={day}&date_to={day}").json()
    assert 0 < r["total"] < meta["rows"] and all(row[3] == day for row in r["rows"])     # delivery_date is the 4th column
    none = c.get("/api/data/rows?table=orders&date_from=1999-01-01&date_to=1999-01-02").json()
    assert none["total"] == 0 and none["rows"] == [] and none["next_offset"] is None
    assert c.get("/api/data/rows?table=orders&date_from=yesterday").status_code == 422
    assert c.get("/api/data/rows?table=vehicles&date_from=2026-01-01").status_code == 422   # no date to filter on


def test_data_rows_refuses_unknown_tables_and_caps_the_page(env):
    c = client(env)
    for bad in ("nope", "sqlite_master", "orders; drop table orders", 'orders" --'):
        r = c.get("/api/data/rows", params={"table": bad})
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    r = c.get("/api/data/rows?table=orders&limit=5000").json()
    assert r["limit"] == 100 and len(r["rows"]) == 100
    assert c.get("/api/data/rows?table=orders&limit=0").status_code == 422
    assert c.get("/api/data/rows?table=orders&offset=-1").status_code == 422
    assert c.get("/api/data/rows?table=orders&company=T02").json()["rows"][0][0].startswith("T02-")


def test_the_orders_panel_lists_the_days_with_open_orders_and_one_day_at_a_time(env):
    c = client(env)
    c.get("/api/session")
    r = c.get("/api/dashboard/orders?company=T01").json()
    assert r["delivery_date"] == r["today"] and r["days"] and r["days"][0]["date"] == r["today"]
    assert r["days"][0]["open"] == len(r["orders"])
    past = c.get("/api/dashboard/orders?company=T01&day=2026-08-01").json()
    assert past["delivery_date"] == r["today"]                                  # a past day falls back to today
    assert c.get("/api/dashboard/orders?company=T01&day=tomorrow").status_code == 422



def test_the_two_workspaces_keep_their_own_lessons_drafts_and_runs_and_only_reset_empties_fresh_start(env, monkeypatch):
    """Nov 4: Fresh start and After learning are two workspaces. Switching never empties either; Reset empties Fresh
    start only; a run belongs to the workspace it ran in."""
    c = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    c.get("/api/session")
    assert c.get("/api/fresh/status?company=T01").json()["fresh"] is True
    live_env(monkeypatch, [mock_final("Nothing to plan yet.")])
    mine = c.post("/api/chat", json={"message": "anything for tomorrow?", "mode": "live", "use_lessons": False}).json()
    list(stream.follow(mine["run_id"]))
    lid = c.get("/api/learning/lessons?company=T01").json()
    assert lid == []                                                             # Fresh start: nothing learned
    learned = c.post("/api/fresh/mode?company=T01&mode=learned").json()
    assert learned["fresh"] is False and learned["lessons"] > 0                  # After learning: the recorded lessons
    assert mine["run_id"] not in {r["run_id"] for r in c.get("/api/logs/runs?company=T01").json()}
    back = c.post("/api/fresh/mode?company=T01&mode=fresh").json()
    assert back["fresh"] is True and back["lessons"] == 0
    assert [r["run_id"] for r in c.get("/api/logs/runs?company=T01").json()] == [mine["run_id"]]   # still there after the round trip
    import time
    time.sleep(1.1)
    c.post("/api/fresh/reset?company=T01")
    assert c.get("/api/logs/runs?company=T01").json() == []                      # Reset empties Fresh start
    again = c.post("/api/fresh/mode?company=T01&mode=learned").json()
    assert again["lessons"] == learned["lessons"]                                # and leaves After learning alone


def test_after_learning_gets_the_recorded_lessons_back_if_an_older_reset_emptied_it(env):
    """Nov 4: before the two workspaces, Reset emptied the visitor's only store, which is now After learning's."""
    from anubhav.service.session import _empty
    c = TestClient(api_app.create_app(public=True, world=env, replay_pace=0, start_fresh=True), raise_server_exceptions=False)
    sid = c.get("/api/session").headers["X-Anubhav-Visitor"]
    full = c.post("/api/fresh/mode?company=T01&mode=learned").json()["lessons"]
    assert full > 0
    store = env / "learning" / "sessions" / f"{sid}.sqlite"
    if not store.exists():
        from anubhav.service import session as sess
        store = sess.state_root(env) / "learning" / "sessions" / f"{sid}.sqlite"
    _empty(store)                                                                 # what an older Reset left behind
    c.post("/api/fresh/mode?company=T01&mode=fresh")
    assert c.post("/api/fresh/mode?company=T01&mode=learned").json()["lessons"] == full
