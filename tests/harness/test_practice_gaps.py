"""Gap questions (D-040, C6): no built tool answers them; answers are computed from the records; held-out
questions don't repeat dev ones; scoring reads the first weekday named, in any of the three languages."""

import pytest

from anubhav.data import generate
from anubhav.harness import practice
from anubhav.runtime.company import CompanyData


@pytest.fixture(scope="module")
def C(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return CompanyData(next(out.iterdir()), "T01", tmp_path_factory.mktemp("rt"))


def test_gap_questions_have_answers_and_held_out_never_repeats_dev(C):
    dev, held = practice.build_gaps(C, split="dev"), practice.build_gaps(C, split="held_out")
    assert {q["type"] for q in dev} == set(practice.GAP_TYPES) and all(q["gap"] for q in dev + held)
    assert not {q["question"] for q in dev} & {q["question"] for q in held}
    assert {q["lang"] for q in dev} == {"rt", "te", "en"}
    assert practice.build(C) == practice.build(C)                       # the frozen practice set is untouched
    assert not any(q.get("gap") for q in practice.build(C))


@pytest.mark.parametrize("reply, ok", [("Thursday is worst (82%), then Wednesday.", True),
                                       ("Guruvaram roju worst, taruvatha Budhavaram.", True),
                                       ("గురువారం అతి తక్కువ.", True),
                                       ("Wednesday 88%, Thursday 82%: Thursday is worst.", False),
                                       ("I could not compute it.", False)])
def test_the_first_weekday_named_is_the_answer(reply, ok):
    q = {"type": "worst_ontime_weekday", "gap": True, "check": {"weekday": 3}}
    r = {"trace": [{"type": "tool", "name": "run_query", "ok": True}], "reply": reply, "cost_usd": 0, "run_id": "x"}
    s = practice.score(q, r)
    assert s["answer_ok"] == ok and s["right_tool"]


def test_a_learned_tool_counts_as_the_fitting_tool_and_a_builtin_does_not():
    q = {"type": "damaged_cases_month", "gap": True, "check": {"number": 17}}
    mk = lambda name: {"trace": [{"type": "tool", "name": name, "ok": True}], "reply": "17 cases", "cost_usd": 0, "run_id": "x"}
    assert practice.score(q, mk("damaged_cases_in_month"))["right_tool"]
    assert not practice.score(q, mk("trip_history"))["right_tool"]
