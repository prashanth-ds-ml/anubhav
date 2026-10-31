"""The framework-free core (B1): no Streamlit in it; visitors are isolated; the spend guard holds; the single Planner and
the team both run, save and produce events through it. Mock model only; no credits."""

import ast
import pathlib

import pytest

from anubhav import events, muse, trace
from anubhav.data import generate
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.service import runs, session
from anubhav.service.session import MODELS, Workspace


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def traces(tmp_path, monkeypatch):
    d = tmp_path / "traces"
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    return d


@pytest.fixture
def ws(world, tmp_path):
    w = tmp_path / "w"
    import shutil
    shutil.copytree(world, w)
    return lambda sid="a", public=True, state=None: Workspace(sid, public, {} if state is None else state, w)


def test_the_service_never_imports_a_web_framework():
    for p in pathlib.Path("src/anubhav/service").glob("*.py"):
        names = {n.name.split(".")[0] for x in ast.walk(ast.parse(p.read_text(encoding="utf-8"))) if isinstance(x, ast.Import) for n in x.names}
        names |= {(x.module or "").split(".")[0] for x in ast.walk(ast.parse(p.read_text(encoding="utf-8"))) if isinstance(x, ast.ImportFrom)}
        assert not names & {"streamlit", "fastapi", "starlette"}, p


def test_visitors_never_see_each_others_drafts_or_lessons(ws):
    a, b = ws("a"), ws("b")
    assert a.company("T01").runtime is not b.company("T01").runtime
    assert a.company("T01").sites is b.company("T01").sites             # the records are shared, read-only
    assert a.store_path() != b.store_path()
    a.store()
    a.clear_lessons()
    assert a.store().list("T01") == [] and b.store().list("T01") != []


def test_locally_the_store_is_shared(ws):
    a, b = ws("x", public=False), ws("y", public=False)
    assert a.store_path() == b.store_path() and a.company("T01").runtime is b.company("T01").runtime


def test_spend_guard_counts_runs_and_stops_at_the_caps(ws, monkeypatch):
    monkeypatch.setenv(muse.KEYS["spark"], "test-key")
    monkeypatch.setattr(muse, "client", lambda name: MockClient([]))
    w = ws()
    for _ in range(session.LIVE_RUNS_PER_SESSION):
        client, blocked = w.live_client("spark")
        assert client and not blocked
    assert w.live_runs_left() == 0
    client, blocked = w.live_client("spark")
    assert client is None and "used its" in blocked
    other = ws("b")
    monkeypatch.setattr(session, "LIVE_CALLS_PER_DAY", session.LIVE_RUNS_PER_SESSION)
    assert "daily budget" in other.live_ready("spark")                    # the day's cap is across visitors


def test_no_key_means_no_client_and_no_count(ws, monkeypatch):
    monkeypatch.delenv(muse.KEYS["spark"], raising=False)
    w = ws()
    client, blocked = w.live_client("spark")
    assert client is None and "Live mode is off" in blocked and w.state.get("live_runs", 0) == 0


def test_a_single_planner_run_is_saved_with_events(ws, traces):
    w = ws()
    r = runs.run_with(w, MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "T01", "sites?", False, harness={})
    assert "mode" not in r and r["learned_tools"] == []
    assert trace.load(r["run_id"], traces)["label"] == "ui:T01:cold"
    assert events.EventStore(traces / "events.sqlite").load(r["run_id"])[0]["type"] == "agent_start"


def test_a_team_run_goes_through_the_same_door_with_lessons_and_guards(ws, traces):
    w = ws()
    client = MockClient([mock_tool_call("delegate", {"agent": "analyst", "brief": "Count our sites per town and return it."}),
                         mock_tool_call("list_sites", {}), mock_final("45"), mock_final("45 sites")])
    r = runs.run_with(w, client, "T01", "sites?", True, team=True, harness={})
    saved = trace.load(r["run_id"], traces)
    assert saved["mode"] == "team" and saved["label"] == "ui:T01:lessons:team" and saved["children"][0]["agent_id"] == "analyst"
    assert saved["knowledge"]                                            # the visitor's approved lessons reached the lead
    assert {e["agent_id"] for e in events.EventStore(traces / "events.sqlite").load(r["run_id"])} == {"planner", "analyst"}


def test_blocked_run_live_raises_and_spends_nothing(ws, monkeypatch):
    monkeypatch.delenv(muse.KEYS["spark"], raising=False)
    with pytest.raises(muse.MissingKeyError):
        runs.run_live(ws(), "T01", "x", "spark", False)


def test_replay_matching_finds_the_bundle_and_prefers_the_same_tool_state(ws, traces):
    w = ws()
    req = session.SUGGESTIONS["New tool"]
    before = runs.find_replay(w, "T01", req, False, learned=False)
    after = runs.find_replay(w, "T01", req, False, learned=True)
    assert before["tool_calls"] > after["tool_calls"] == 1
    assert runs.find_replay(w, "T01", "something never asked", False) is None
    assert "New tool" in runs.replayable(w, "T01", False)
    assert runs.find_run(before["run_id"])["run_id"] == before["run_id"] and runs.find_run("nope") is None


def test_both_models_can_be_picked_live_and_meta_is_the_default(monkeypatch, tmp_path):
    """Judges can try either model; both go through the same spend guard."""
    for key in muse.KEYS.values():
        monkeypatch.setenv(key, "test-key")
    w = Workspace(world=tmp_path)
    assert session.AGENT_MODEL == "spark" and {"spark", "open"} <= set(MODELS.values())
    assert w.live_ready("spark") is None and w.live_ready("open") is None
    w.live_client("open")
    w.live_client("spark")
    assert w.state["live_runs"] == 2 and w.calls_today() == 2
