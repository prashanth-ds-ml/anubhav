"""Live streaming (B2): events appear while the run is still going, the live stream equals the saved run's stream,
a reader can reconnect, and a crashed run still ends. Mock model only; no credits."""

import json
import threading

import jsonschema
import pytest

from anubhav import events, trace
from anubhav.agent import graph
from anubhav.agents import team
from anubhav.data import generate
from anubhav.data.config import ROOT
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.service import stream
from anubhav.service.session import Workspace


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


@pytest.fixture
def traces(tmp_path, monkeypatch):
    d = tmp_path / "traces"
    monkeypatch.setattr(trace, "TRACE_DIR", d)
    monkeypatch.setattr(trace.save, "__defaults__", (d, "live"))
    d.mkdir()
    return d


def strip(ev):
    return [{k: v for k, v in e.items() if k != "ts"} for e in ev]


SCRIPT = lambda: [mock_tool_call("find_capability", {"need": "xylophone quantum"}),
                  mock_tool_call("delegate", {"agent": "tool_forge", "brief": "Count our sites per town and return it."}),
                  mock_tool_call("get_order", {"order_id": "NOPE"}), mock_tool_call("get_order", {"order_id": "NOPE2"}),
                  mock_final("45"), mock_final("45 sites")]


def test_live_events_equal_the_saved_runs_events_for_a_team(C):
    em = events.Emitter("x")
    r = team.run(C, Session("T01"), MockClient(SCRIPT()), "sites?", hooks=em, run_id="x")
    assert r["run_id"] == "x" and strip(em.events) == strip(events.from_run(r))
    schema = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))
    for e in em.events:
        jsonschema.validate(e, schema)
    assert {"handoff", "tool_missing", "retry"} <= {e["type"] for e in em.events}


def test_live_events_equal_the_saved_runs_events_for_a_draft_and_the_baseline(C):
    b = Broker(C, Session("T01"))
    orders = b.call("list_open_orders", {})["result"]["orders"]
    free = b.call("list_vehicles", {"available_on": C.today})["result"]["vehicles"]
    pick = next(v for v in sorted(free, key=lambda v: -v["payload_kg"]))
    em = events.Emitter("y")
    r = graph.run(b, MockClient([mock_tool_call("create_dispatch_draft", {"order_ids": [orders[0]["order_id"]], "vehicle_id": pick["vehicle_id"]}),
                                 mock_final("draft")]), "plan", hooks=em, run_id="y")
    types = [e["type"] for e in em.events]
    assert strip(em.events) == strip(events.from_run(r)) and ("draft_created" in types or "validator_check" in types)


def test_hooks_change_nothing_for_the_agent(C):
    plain = graph.run(Broker(C, Session("T01")), MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "x")
    heard = graph.run(Broker(C, Session("T01")), MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "x", hooks=events.Emitter("z"))
    assert plain["reply"] == heard["reply"] and [s["type"] for s in plain["trace"]] == [s["type"] for s in heard["trace"]]
    assert plain["trace"][1]["result"] == heard["trace"][1]["result"]


def test_events_are_readable_while_the_run_is_still_going(world, tmp_path, traces):
    gate, seen = threading.Event(), threading.Event()

    def wait_for_test(msgs, tools):
        seen.set()                                  # the tool has run; hold the model here
        assert gate.wait(30)
        return mock_final("ok")
    client = MockClient([mock_tool_call("list_sites", {}), wait_for_test])
    ws = Workspace("a", True, {}, world)
    run_id = stream.start(ws, client, "T01", "sites?", False, harness={})
    assert seen.wait(30)
    mid = stream.store().load(run_id)
    assert [e["type"] for e in mid] == ["agent_start", "tool_call", "tool_result"] and stream.status(run_id)["status"] == "running"
    gate.set()
    got = list(stream.follow(run_id))
    assert got[-1]["type"] == "agent_done" and [e["seq"] for e in got] == list(range(len(got)))
    assert stream.status(run_id)["status"] == "done" and stream.ended_stop(run_id) == "answered"
    assert trace.load(run_id, traces)["run_id"] == run_id
    assert got[0]["ts"] is not None                 # the save stamped them


def test_a_reader_can_reconnect_and_gets_only_what_it_missed(world, traces):
    ws = Workspace("a", True, {}, world)
    run_id = stream.start(ws, MockClient([mock_tool_call("list_sites", {}), mock_final("ok")]), "T01", "sites?", False, harness={})
    full = list(stream.follow(run_id))
    assert [e["seq"] for e in stream.follow(run_id, after=1)] == [e["seq"] for e in full[2:]]


def test_a_crashed_run_still_ends_for_the_reader(world, traces, monkeypatch):
    monkeypatch.setattr(stream.runs, "run_with", lambda *a, **k: 1 / 0)
    ws = Workspace("a", True, {}, world)
    run_id = stream.start(ws, MockClient([]), "T01", "x", False, harness={})
    assert list(stream.follow(run_id, poll_s=0.01, timeout_s=10)) == []
    assert stream.status(run_id)["stop"] == "error" and stream.status(run_id)["error"] == "ZeroDivisionError"


def test_a_failed_model_call_is_still_a_clean_end(world, traces):
    ws = Workspace("a", True, {}, world)
    run_id = stream.start(ws, MockClient([]), "T01", "x", False, harness={})
    got = list(stream.follow(run_id))
    assert got[-1]["type"] == "agent_done" and got[-1]["payload"]["stop"] == "error"


def test_replay_events_resume_too():
    run = next(json.loads(x) for x in (ROOT / "demo" / "replay_runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())
    full = stream.replay_events(run)
    assert full[0]["type"] == "agent_start" and [e["seq"] for e in stream.replay_events(run, after=2)] == [e["seq"] for e in full[3:]]
