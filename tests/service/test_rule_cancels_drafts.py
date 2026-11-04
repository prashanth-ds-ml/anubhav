"""EXP-021: approving an enforced site-length rule cancels the open drafts it forbids, and only those."""
import json
from types import SimpleNamespace

from anubhav.service import fresh


class Runtime:
    def __init__(self, drafts):
        self.rows = drafts

    def drafts(self):
        return self.rows

    def cancel(self, draft_id):
        row = next(d for d in self.rows if d["draft_id"] == draft_id)
        if row["status"] != "draft":
            return False
        row["status"] = "cancelled"
        return True


def company():
    drafts = [
        {"draft_id": "D32", "status": "draft", "vehicle_id": "V11", "order_ids": json.dumps(["O1"])},      # 32 ft at the gate site
        {"draft_id": "D22", "status": "draft", "vehicle_id": "V08", "order_ids": json.dumps(["O1"])},      # 22 ft: allowed
        {"draft_id": "DOK", "status": "approved", "vehicle_id": "V11", "order_ids": json.dumps(["O1"])},   # a person approved it
        {"draft_id": "DXX", "status": "draft", "vehicle_id": "V11", "order_ids": json.dumps(["O2"])},      # another site
    ]
    return SimpleNamespace(runtime=Runtime(drafts), vehicles={"V11": {"length_ft": 32}, "V08": {"length_ft": 22}},
                           orders={"O1": {"site_id": "C0003"}, "O2": {"site_id": "C0009"}})


RULE = {"kind": "site_access", "params": {"site_id": "C0003", "max_length_ft": 22}}


def test_an_enforced_gate_rule_cancels_only_the_open_drafts_it_forbids():
    C = company()
    assert fresh.cancel_breaking(C, RULE) == ["D32"]
    status = {d["draft_id"]: d["status"] for d in C.runtime.rows}
    assert status == {"D32": "cancelled", "D22": "draft", "DOK": "approved", "DXX": "draft"}


def test_other_kinds_of_lesson_cancel_nothing():
    C = company()
    assert fresh.cancel_breaking(C, {"kind": "alias", "params": {"site_id": "C0003"}}) == []
    assert all(d["status"] != "cancelled" for d in C.runtime.rows)
