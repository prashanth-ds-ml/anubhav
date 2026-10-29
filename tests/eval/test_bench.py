"""The benchmark's cases and its scoring must be right before any result is trusted. Mock model only."""

import pytest

from anubhav.data import generate
from anubhav.eval import bench
from anubhav.muse import MockClient, mock_final, mock_tool_call


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


def test_cases_cover_every_family_and_language(world):
    cases = bench.build(world)
    fams = {c["family"] for c in cases}
    assert fams == {"site_access", "alias", "real_capacity", "control", "look_alike"}
    assert {c["lang"] for c in cases if c["family"] == "site_access"} == {"rt", "te", "en"}


def test_prepare_leaves_exactly_one_open_order_at_the_site(world, tmp_path):
    case = next(c for c in bench.build(world) if c["family"] == "site_access")
    C, oid = bench.prepare(world, case, tmp_path)
    open_here = [o for o in C.orders.values() if o["site_id"] == case["site_id"] and o["status"] == "open"]
    assert [o["order_id"] for o in open_here] == [oid] and 6000 < C.order_load(oid)["kg"] < 7600


def _draft_with(world, tmp_path, case, length_ft):
    C, oid = bench.prepare(world, case, tmp_path)
    v = next(v for v in C.vehicles.values() if v["length_ft"] == length_ft and v["payload_kg"] >= case["kg"]
             and v["status"] == "available" and min(v[k] for k in ("fitness_until", "permit_until", "insurance_until", "puc_until")) >= C.today)
    return MockClient([mock_tool_call("create_dispatch_draft", {"order_ids": [oid], "vehicle_id": v["vehicle_id"]}), mock_final("ok")])


def test_scoring_marks_a_long_truck_at_a_limited_site_unsafe_and_a_short_one_safe(world, tmp_path):
    case = next(c for c in bench.build(world) if c["family"] == "site_access" and c["company"] == "T01")
    bad = bench.run_case(world, case, _draft_with(world, tmp_path / "a", case, 32), "B", runtime_dir=tmp_path / "a")
    good = bench.run_case(world, case, _draft_with(world, tmp_path / "b", case, 22), "B", runtime_dir=tmp_path / "b")
    assert bad["unsafe"] and not bad["ok"] and good["ok"] and not good["unsafe"]


def test_no_draft_is_not_ok_but_not_unsafe(world, tmp_path):
    case = next(c for c in bench.build(world) if c["family"] == "control")
    r = bench.run_case(world, case, MockClient([mock_final("which site?")]), "A", runtime_dir=tmp_path)
    assert not r["ok"] and not r["unsafe"]


def test_arm_a_has_no_raw_note_search(world, tmp_path):
    case = next(c for c in bench.build(world) if c["family"] == "control")
    seen = {}
    def step(msgs, tools):
        seen["tools"] = {t["function"]["name"] for t in tools}
        return mock_final("ok")
    bench.run_case(world, case, MockClient([step]), "A", runtime_dir=tmp_path)
    assert "search_notes" not in seen["tools"] and "list_open_orders" in seen["tools"]
