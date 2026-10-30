"""The activity log is built only from recorded data: a run becomes plan → act → observe rows with refusals and the
code checks marked; lesson events, patches and feedback join one timeline per company."""

from anubhav.ui import logs

RUN = {"run_id": "r1", "company": "T01", "model": "meta-models/muse-spark-open", "request": "plan", "saved_at": "2026-10-31T10:00:00",
       "stop": "answered", "drafts": ["DR-1"], "cost_usd": 0.01, "knowledge": [],
       "reply_check": {"ok": False, "unknown_ids": ["V99"], "claims": []},
       "trace": [
           {"type": "model", "turn": 1, "content": "", "tool_calls": [{"name": "create_dispatch_draft", "arguments": "{}"}]},
           {"type": "tool", "name": "create_dispatch_draft", "arguments": '{"vehicle_id": "V01"}', "ok": False,
            "result": None, "error": {"code": "CAPACITY_EXCEEDED", "message": "too heavy. Next step: V13"}},
           {"type": "tool", "name": "create_dispatch_draft", "arguments": {"vehicle_id": "V13"}, "ok": True,
            "result": {"draft_id": "DR-1"}, "error": None},
           {"type": "model", "turn": 2, "content": "Draft DR-1 on V99", "tool_calls": []},
           {"type": "finish", "draft_checks": [{"draft_id": "DR-1", "still_valid": True, "errors": [], "held": True}],
            "reply_check": {"ok": False, "unknown_ids": ["V99"], "claims": []}}]}


def test_a_run_reads_as_plan_act_observe_with_refusals_and_checks():
    kinds = [r["kind"] for r in logs.timeline(RUN)]
    assert kinds == ["plan", "act", "refused", "act", "observe", "answer", "check", "check"]
    rows = logs.timeline(RUN)
    assert "Next step: V13" in rows[2]["text"]
    assert rows[-1]["ok"] is False and "V99" in rows[-1]["text"]


def test_events_join_runs_lessons_patches_and_feedback_for_one_company_newest_first():
    ev = [{"ts": "2026-10-31T11:00:00", "lesson_id": "L-T01-001", "company": "T01", "actor": "gate", "action": "propose",
           "from_state": None, "to_state": "CANDIDATE", "note": "3 for, 0 against"},
          {"ts": "2026-10-31T12:00:00", "lesson_id": "L-T02-001", "company": "T02", "actor": "gate", "action": "propose",
           "from_state": None, "to_state": "CANDIDATE", "note": ""}]
    versions = [{"version_id": "h-000", "created": "x"},
                {"version_id": "h-001", "created": "2026-10-31T09:00:00", "rationale": "fewer repeats", "status": "rejected",
                 "probe": {"gate": {"pass": False, "reasons": ["no held-out gain"]}}, "decided": "2026-10-31T09:30:00",
                 "decided_by": "owner", "note": ""}]
    fb = [{"ts": "2026-10-31T13:00:00", "company": "T01", "rating": 0, "request": "plan", "category": "wrong_tool",
           "note": "too many calls", "status": "new", "run_id": "r1", "source": "tester"}]
    out = logs.events("T01", runs=[RUN, dict(RUN, company="T02")], lesson_events=ev, versions=versions, feedback=fb)
    assert [e["stream"] for e in out] == ["feedback", "lesson", "run", "harness", "harness", "harness"]
    assert "reply check failed" in out[2]["detail"] and "1 refused" in out[2]["detail"]
    assert [e["what"] for e in out[3:]] == ["patch h-001 rejected", "patch h-001 tested old vs new", "patch h-001 proposed"]
    assert "no held-out gain" in out[4]["detail"]
