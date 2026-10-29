"""Tool practice: questions come from the company's data, dev and held-out don't overlap, the proposer never sees
the expected tools, and the gate requires held-out improvement without regressions."""

import pytest

from anubhav.data import generate
from anubhav.harness import practice
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import REGISTRY
from anubhav.runtime.company import CompanyData


@pytest.fixture(scope="module")
def C(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return CompanyData(next(out.iterdir()), "T01", tmp_path_factory.mktemp("rt"))


def test_questions_come_from_data_and_splits_do_not_overlap(C):
    dev, held = practice.build(C, split="dev"), practice.build(C, split="held_out")
    assert len(dev) >= 12 and len(held) >= 12
    assert not {q["question"] for q in dev} & {q["question"] for q in held}
    assert "towns_served" not in {q["type"] for q in held}
    assert {q["lang"] for q in dev} == {"rt", "te", "en"}
    tools = {t.name for t in REGISTRY}
    assert all(practice.TYPES[q["type"]]["tools"] <= tools for q in dev)


def test_number_answers_ignore_dates_ids_and_list_markers():
    assert practice._numbers("1. T01-O00879 on 2026-10-30 at 10:00: 3 orders") == {3}


def _run(reply, tools=(), ok=True):
    trace = [{"type": "tool", "name": t, "ok": ok, "error": None if ok else {"code": "BAD_ARGS", "message": "x"}} for t in tools]
    return {"reply": reply, "trace": trace, "cost_usd": 0.01, "run_id": "r"}


def test_scoring():
    q = {"type": "trips_in_month", "check": {"number": 22}}
    s = practice.score(q, _run("Kazipet lo September lo 22 deliveries", ["trip_history"]))
    assert s["answer_ok"] and s["right_tool"] and s["used_tool"]
    s = practice.score(q, _run("I don't have history data"))
    assert not s["answer_ok"] and not s["used_tool"]
    q2 = {"type": "sites_in_town", "check": {"names_any": ["A Traders", "B Stores", "C Mart"], "min_share": 0.6}}
    assert practice.score(q2, _run("A Traders, B Stores", ["list_sites"]))["answer_ok"]


def test_proposer_sees_what_went_wrong_but_never_the_expected_tool():
    results = [{"question": "q1", "type": "trips_in_month", "tools": ["list_open_orders"], "used_tool": True, "tool_errors": 0,
                "answer_ok": False, "reply": "only tomorrow"},
               {"question": "q2", "type": "trips_in_month", "tools": [], "used_tool": False, "tool_errors": 0,
                "answer_ok": False, "reply": "no data"}]
    out = practice.failures_for_proposer(results)
    assert [o["what_went_wrong"] for o in out] == ["the answer did not match the company's records",
                                                   "answered without looking anything up"]
    assert "trip_history" not in str(out) and "type" not in out[0]


def test_gate_needs_held_out_improvement_and_no_regressions():
    base = {"answer_ok": 0.5, "tool_errors": 1, "cost_usd": 0.3}
    better = {"answer_ok": 0.8, "tool_errors": 1, "cost_usd": 0.35}
    assert practice.gate(base, better, {"golden": ["V08"]}, {"golden": ["V08"]})["pass"]
    assert not practice.gate(base, base, {}, {})["pass"]
    assert not practice.gate(base, better, {"golden": ["V08"]}, {"golden": []})["pass"]
    assert not practice.gate(base, dict(better, tool_errors=3), {}, {})["pass"]


def test_practice_run_with_a_mock_model(C):
    q = practice.build(C, split="dev")[0]
    names = q["check"]["names_any"]
    m = MockClient([mock_tool_call("list_sites", {"town": "x"}), mock_final(", ".join(names))])
    res = practice.run(C, m, [q])
    assert res[0]["answer_ok"] and res[0]["right_tool"] and practice.summary(res)["answer_ok"] == 1.0
