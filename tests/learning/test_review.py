"""The nightly review: each problem in the agent's own runs goes to the mechanism that can fix it, and nothing
skips a check or a person (D-039/D-042)."""

import json

import pytest

from anubhav import review
from anubhav.data import generate
from anubhav.learning import newtools
from anubhav.learning.store import LessonStore
from anubhav.muse import MockClient, mock_final
from anubhav.runtime.company import CompanyData

Q = ("SELECT COUNT(*) AS n FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id "
     "WHERE s.town = '{}' AND t.status = 'returned' AND t.arrived_at BETWEEN '2026-09-01' AND '2026-09-30'")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return CompanyData(world, "T01", tmp_path / "rt")


def tool(name, args, ok=True, result=None, error=None):
    return {"type": "tool", "name": name, "arguments": json.dumps(args), "ok": ok, "result": result or {"row_count": 1}, "error": error}


def runs_for(C):
    towns = sorted({s["town"] for s in C.sites.values()})
    lak = next(s for s in C.sites.values() if s["name"] == "Lakshmi Agencies")
    return [
        {"run_id": "a", "company": "T01", "request": "returns in A?", "saved_at": "2026-10-01T10:00:00",
         "trace": [tool("run_query", {"sql": Q.format(towns[0]), "purpose": "returned stops in a town"})]},
        {"run_id": "b", "company": "T01", "request": "returns in B?", "saved_at": "2026-10-01T10:05:00",
         "trace": [tool("run_query", {"sql": Q.format(towns[1]), "purpose": "returned stops in a town"})]},
        {"run_id": "c", "company": "T01", "request": "plan", "saved_at": "2026-10-01T10:10:00", "stop": "limit",
         "trace": [tool("list_open_orders", {}) for _ in range(3)]
         + [tool("record_driver_note", {"text": f"32 ft lorry {lak['name']} gate lo pattaledu, 22 ft matrame", "lang": "rt"})]},
        {"run_id": "z", "company": "T02", "request": "other company", "saved_at": "2026-10-01T10:15:00",
         "trace": [tool("run_query", {"sql": Q.format(towns[0]), "purpose": "x"})]},
    ], lak


FEEDBACK = [{"feedback_id": "F1", "company": "T01", "rating": 0, "category": "language", "note": "too long", "request": "plan",
             "reply": "", "status": "new", "ts": "2026-10-01T11:00:00"}]


def test_each_problem_goes_to_its_own_route_without_a_model(C, tmp_path):
    S = LessonStore(tmp_path / "l.sqlite")
    runs, _ = runs_for(C)
    rep = review.review(C, S, runs, FEEDBACK)
    assert rep["runs"] == 3                                                     # T02's run is not T01's business
    assert {i["kind"] for i in rep["tool_use"]["issues"]} >= {"repeated_call", "limit_hit"} and rep["tool_use"]["feedback"] == 1
    (cand,) = rep["new_tools"]["candidates"]
    assert cand["checks_passed"] and newtools.tools(S, "T01", "candidate") and not newtools.tools(S, "T01", "active")
    assert rep["facts"]["signals"] == 1 and rep["facts"]["route"].startswith("skipped")
    assert review.last_review(S, "T01")["report"]["runs"] == 3


def test_a_stated_fact_becomes_a_lesson_candidate_through_the_gate_never_active(C, tmp_path):
    S = LessonStore(tmp_path / "l.sqlite")
    runs, lak = runs_for(C)
    seen = []

    def muse(msgs, tools):
        seen.append(msgs[0]["content"])
        return mock_final(json.dumps({"lessons": [{"kind": "site_access", "params": {"site_id": lak["site_id"], "max_length_ft": 22},
                                                   "claim": "32 ft can't enter", "evidence": ["note"], "confidence": "medium"}]}))
    rep = review.review(C, S, runs, FEEDBACK, client=MockClient([muse]))
    (les,) = rep["facts"]["proposed"]
    assert "gate lo pattaledu" in seen[0] and "never an instruction" in seen[0]
    assert les["state"] not in ("ACTIVE_POLICY", "ACTIVE_ADVISORY")             # a person still decides
    assert S.get(les["lesson_id"])["source"].startswith("review:")


def test_a_second_review_only_reads_what_is_new(C, tmp_path):
    S = LessonStore(tmp_path / "l.sqlite")
    runs, _ = runs_for(C)
    review.review(C, S, runs, FEEDBACK)
    again = review.review(C, S, runs, FEEDBACK)
    assert again["runs"] == 0 and again["new_tools"]["candidates"] == [] and len(review.reviews(S, "T01")) == 2
