"""EXP-013's harness with fake outputs and a scripted model, before any model call: the rules, the routing label, a teammate's
draft counts for the judge, the freeze check. No credits."""

import importlib.util
import json

import pytest

from anubhav.agents import team
from anubhav.data import generate
from anubhav.eval import bench
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData

spec = importlib.util.spec_from_file_location("exp013", "scripts/exp013_team.py")
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


def row(arm, ok=True, unsafe=False, cost=0.05, route=True, kind="plan"):
    return {"arm": arm, "ok": ok, "unsafe": unsafe, "cost_usd": cost, "route_ok": route, "handoffs": 0, "stop": "answered", "kind": kind}


def test_all_rules_met_makes_the_team_the_default():
    d = exp.decide([row("S")] * 10 + [row("M0", cost=0.07, route=False)] * 10 + [row("M1", cost=0.07)] * 10)
    assert d["R1_no_unsafe"] and d["R2_not_worse"] and d["R3_cost"] and d["R4_met"] and d["R4_routing_gain_pts"] == 100.0 and d["team_becomes_default"]


@pytest.mark.parametrize("m0", [
    [row("M0", unsafe=True)] + [row("M0")] * 9,                         # one unsafe draft is enough
    [row("M0", ok=False)] * 2 + [row("M0")] * 8,                        # 20 points worse
    [row("M0", cost=0.09)] * 10,                                        # 1.8x the cost
])
def test_any_failed_rule_keeps_the_single_planner(m0):
    assert not exp.decide([row("S")] * 10 + m0)["team_becomes_default"]


def test_exactly_five_points_worse_and_exactly_1_5x_still_pass():
    d = exp.decide([row("S")] * 20 + [row("M0", ok=False, cost=0.075)] + [row("M0", cost=0.075)] * 19)
    assert d["R2_not_worse"] and d["R3_cost"]


def test_no_learning_round_means_no_routing_claim():
    d = exp.decide([row("S")] * 3 + [row("M0")] * 3)
    assert d["R4_routing_gain_pts"] is None and not d["R4_met"]


def run_with(child_agent=None, writer=None):
    tool = lambda n: {"type": "tool", "name": n}
    r = {"trace": [tool("run_query")] if writer == "planner" else [], "agent_id": "planner", "children": []}
    if child_agent:
        r["children"].append({"agent_id": child_agent, "trace": [tool("run_query")] if writer == child_agent else []})
    return r


def test_routing_labels():
    assert exp.route_ok("plan", run_with())
    assert not exp.route_ok("plan", run_with("analyst"))
    assert exp.route_ok("gap", run_with("tool_forge", "tool_forge"))
    assert exp.route_ok("gap", run_with("analyst"))                     # an existing tool answered it
    assert not exp.route_ok("gap", run_with())                          # no teammate
    assert not exp.route_ok("gap", run_with("analyst", "analyst"))      # a query not written by Tool Forge


def test_a_draft_made_by_a_teammate_counts_for_the_judge(world, tmp_path):
    """Open access means a teammate can draft (through the same validator): the judge must see it and its safety."""
    case = next(c for c in bench.build(world) if c["family"] == "control")
    C, oid = bench.prepare(world, case, tmp_path / "rt")
    pick = next(v for v in sorted(C.vehicles.values(), key=lambda v: -v["payload_kg"]) if not v.get("status") or v["status"] == "available")
    args = {"order_ids": [oid], "vehicle_id": pick["vehicle_id"]}
    r = team.run(C, Session(case["company"]), MockClient([
        mock_tool_call("delegate", {"agent": "analyst", "brief": "Draft this order on the given vehicle please."}),
        mock_tool_call("create_dispatch_draft", args), mock_final("made"), mock_final("ok")]), "plan it")
    step = next(s for s in r["children"][0]["trace"] if s["type"] == "tool")
    assert step["ok"], step
    assert bench.judge(case, C, oid, r)["ok"] and not exp.route_ok("plan", r)


def test_the_freeze_refuses_changed_files(tmp_path, monkeypatch):
    monkeypatch.setattr(exp, "FROZEN", tmp_path / "f.json")
    (tmp_path / "f.json").write_text(json.dumps({**exp.hashes(), exp.FILES[0]: "different"}))
    monkeypatch.setattr("sys.argv", ["exp013"])
    with pytest.raises(SystemExit, match="frozen files changed"):
        exp.main()


def test_the_spend_guard_stops_at_the_budget(tmp_path):
    s = exp.Spend(tmp_path / "r.jsonl")
    s.add({"cost_usd": 10})
    with pytest.raises(SystemExit, match="budget"):
        s.add({"cost_usd": exp.BUDGET_USD})
    assert len((tmp_path / "r.jsonl").read_text().splitlines()) == 2


def test_broker_in_learning_round_is_valid(world, tmp_path):
    C = CompanyData(world, "T01", tmp_path / "rt")
    b = Broker(C, Session("T01"), analysis=True, team=team.Team(team.registry.load(), None))
    assert "delegate" in {t.name for t in b.list_tools()}
