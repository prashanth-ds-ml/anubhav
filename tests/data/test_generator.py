"""Tests for the world generator: structure, truth vs known, integrity, leaks, evidence, reproducibility,
schema round-trips, and mutation tests that prove the validators catch broken data."""

import copy
import sqlite3
from collections import Counter

import pytest

from anubhavam.data import config, generate, store, validate, world

PILOT = (["T01"], "2026-09-08", "2026-09-14")


@pytest.fixture(scope="module")
def cfg():
    return config.load()


@pytest.fixture(scope="module")
def pilot(cfg):
    return generate.generate(cfg, *PILOT)


# ---------- config and randomness
def test_config_hash_is_stable(cfg):
    assert config.config_hash(cfg) == config.config_hash(config.load())


def test_substreams_are_independent(cfg):
    a = [config.rng(cfg, "notes", "T01").random() for _ in range(3)]
    b = [config.rng(cfg, "demand", "T01").random() for _ in range(3)]
    assert a != b and a == [config.rng(cfg, "notes", "T01").random() for _ in range(3)]
    with pytest.raises(ValueError):
        config.rng(cfg, "nope")


# ---------- world
def test_world_ids_unique_and_anchors_present(cfg):
    W = world.build(cfg)
    assert len({(s["company"], s["site_id"]) for s in W.sites}) == len(W.sites)
    assert len({(v["company"], v["vehicle_id"]) for v in W.vehicles}) == len(W.vehicles)
    for a in cfg["anchor_sites"]:
        for c in a["companies"]:
            assert W.site_by_key(c, a["id"]), (c, a["id"])


def test_warangal_companies_share_a_modest_number_of_sites(cfg):
    W = world.build(cfg)
    t01 = {s["site_key"] for s in W.sites if s["company"] == "T01"}
    t02 = {s["site_key"] for s in W.sites if s["company"] == "T02"}
    t03 = {s["site_key"] for s in W.sites if s["company"] == "T03"}
    assert 0.15 <= len(t01 & t02) / len(t01) <= 0.35
    assert not t03 & t01


def test_pilot_world_matches_full_world_for_t01(cfg):
    full = [(s["site_id"], s["name"], s["town"]) for s in world.build(cfg).sites if s["company"] == "T01"]
    pilot = [(s["site_id"], s["name"], s["town"]) for s in world.build(cfg, ["T01"]).sites]
    assert full == pilot


def test_known_profile_never_states_a_hidden_rule_correctly_at_start(cfg):
    W = world.build(cfg)
    for r in W.rules:
        for s in W.sites:
            if r["kind"] == "site_access" and r["site"] == s["site_key"]:
                assert s["known"]["max_vehicle_length_ft"] != r["max_length_ft"]
            if r["kind"] == "receiving_hours" and r["site"] == s["site_key"]:
                assert s["known"]["receiving_until_hour"] != r["until_hour"]


def test_known_profiles_are_mostly_blank(cfg):
    W = world.build(cfg)
    vals = [v for s in W.sites for v in s["known"].values()]
    assert 0.6 <= sum(v is None for v in vals) / len(vals) <= 0.85


def test_hidden_rules_resolve(cfg):
    W = world.build(cfg)
    for rid in ("H-03", "H-04", "H-05", "H-06", "H-14", "H-22", "H-25"):
        assert all(W.rule(rid)["resolved"].values()), rid
    assert W.vehicle("T01", W.rule("H-14")["resolved"]["T01"])["real_payload_kg"] == 12000


# ---------- pilot run
def test_pilot_is_clean(pilot):
    W, t = pilot
    assert validate.integrity(W, t) == []
    assert validate.leaks(W, t) == []


def test_pilot_has_planned_evidence(pilot):
    W, t = pilot
    ev = validate.evidence(W, t, *PILOT)
    assert ev["H-01"]["failures"] >= 1          # Sep 12 Jangaon, 32 ft
    assert ev["H-16"]["failures"] >= 1          # Tuesday Sep 8, Parkal closed
    assert ev["H-02"]["successes_long"] >= 1    # the other Jangaon site takes long trucks fine
    assert ev["H-03"]["mentions"] >= 1          # "Pedda godown" is used
    assert validate.evidence_problems(ev, W) == []


def test_pilot_volume_and_rhythm(pilot):
    W, t = pilot
    days = len({o["delivery_date"] for o in t["orders"]})
    assert 6 <= len([o for o in t["orders"] if not o.get("_resend")]) / days <= 14
    assert t["replans"], "a real week has re-plans"
    assert all(s["plan_date"] < s["delivery_date"] for s in t["shipments"])


def test_text_is_multilingual_and_messy(pilot):
    W, t = pilot
    langs = Counter(m["lang"] for m in t["planner_messages"] + t["driver_notes"])
    assert set(langs) == {"rt", "te", "en"} and langs["rt"] == max(langs.values())
    assert any(n["source"] == "voice" for n in t["driver_notes"])
    assert any("ి" in m["text"] or "ా" in m["text"] for m in t["planner_messages"] + t["driver_notes"])  # Telugu script


def test_staff_edits_are_daily_small_and_timed_after_events(pilot):
    W, t = pilot
    per_day = Counter(e["ts"][:10] for e in t["staff_edits"])
    assert max(per_day.values()) <= 12
    arrivals = {(o["shipment_id"], o["site_id"]): o["arrived_at"] for o in t["trip_outcomes"]}
    for e in t["staff_edits"]:
        assert "old" != e["old"] or e["new"] != "new"           # no placeholder values
        if e["entity"] == "site" and e["reason_code"] in ("site_access", "weekly_off", "receiving_hours"):
            assert any(e["ts"] > a for (_, sid), a in arrivals.items() if sid == e["entity_id"])


# ---------- reproducibility
def test_same_seed_same_data(cfg, pilot):
    W, t = pilot
    W2, t2 = generate.generate(cfg, *PILOT)
    assert generate.snapshot_hash(W, t, "T01") == generate.snapshot_hash(W2, t2, "T01")


def test_different_seed_different_data(cfg, pilot):
    W, t = pilot
    W2, t2 = generate.generate(config.load(master_seed=7), *PILOT)
    assert generate.snapshot_hash(W, t, "T01") != generate.snapshot_hash(W2, t2, "T01")


def test_changing_notes_never_changes_trips(cfg, pilot):
    W, t = pilot
    W2, t2 = generate.generate(config.load(voice_note_share=0.9, wrong_or_vague_note_share=0.5), *PILOT)
    strip = lambda rows: [{k: v for k, v in r.items()} for r in rows]
    assert strip(t["shipments"]) == strip(t2["shipments"])
    assert strip(t["trip_outcomes"]) == strip(t2["trip_outcomes"])
    assert [n["text"] for n in t["driver_notes"]] != [n["text"] for n in t2["driver_notes"]]


# ---------- export
@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_physical_schema_round_trips(pilot, variant):
    W, t = pilot
    view = store.company_view(W, t, "T01")
    back = store.to_canonical(store.to_physical(view, variant), variant)
    assert back == view


def test_exported_database_has_no_hidden_columns(pilot, tmp_path):
    W, t = pilot
    files = store.write_all(W, t, tmp_path)
    con = sqlite3.connect(files["T01"])
    for (name,) in con.execute("select name from sqlite_master where type='table'"):
        cols = [c[1] for c in con.execute(f'pragma table_info("{name}")')]
        assert not set(cols) & store.HIDDEN_COLUMNS, name
        assert not any(c.startswith("_") for c in cols), name
    assert "replans" not in [n for (n,) in con.execute("select name from sqlite_master")]
    con.close()
    assert (tmp_path / "truth" / "hidden_rules.json").exists()


# ---------- mutation tests: break the data on purpose, the validators must notice
def _mutated(pilot, fn):
    W, t = pilot
    t2 = copy.deepcopy(t)
    fn(W, t2)
    return W, t2


def test_validator_catches_duplicate_order_id(pilot):
    W, t = _mutated(pilot, lambda W, t: t["orders"].append(dict(t["orders"][0])))
    assert any("duplicate" in p for p in validate.integrity(W, t))


def test_validator_catches_negative_quantity(pilot):
    W, t = _mutated(pilot, lambda W, t: t["order_items"][0].update(delivered_cases=-1))
    assert any("negative" in p for p in validate.integrity(W, t))


def test_validator_catches_vehicle_in_two_trips(pilot):
    def clash(W, t):
        a, b = t["shipments"][0], t["shipments"][1]
        b["vehicle_id"] = a["vehicle_id"]
        first = min(e["ts"] for e in t["trip_events"] if e["shipment_id"] == a["shipment_id"])
        for e in t["trip_events"]:
            if e["shipment_id"] == b["shipment_id"]:
                e["ts"] = first
    W, t = _mutated(pilot, clash)
    assert any("two trips at once" in p for p in validate.integrity(W, t))


def test_validator_catches_note_before_trip(pilot):
    W, t = _mutated(pilot, lambda W, t: t["driver_notes"][0].update(ts="2026-01-01T00:00"))
    assert any("before its trip" in p for p in validate.integrity(W, t))


def test_validator_catches_food_mixed_with_chemicals(pilot):
    def mix(W, t):
        sid = t["shipments"][0]["shipment_id"]
        chem = next(p["sku"] for p in W.products if p["handling_class"] == "chemical")
        food = next(p["sku"] for p in W.products if p["handling_class"] == "dense_food")
        t["shipment_items"] += [{"company": "T01", "shipment_id": sid, "order_id": "X", "sku": chem, "cases": 0},
                                {"company": "T01", "shipment_id": sid, "order_id": "X", "sku": food, "cases": 0}]
    W, t = _mutated(pilot, mix)
    assert any("mixes food and chemicals" in p for p in validate.integrity(W, t))


def test_validator_catches_missing_eway_bill(pilot):
    W, t = _mutated(pilot, lambda W, t: t["eway_bills"].clear())
    assert any("e-way bill" in p for p in validate.integrity(W, t))


def test_leak_check_catches_rule_id_in_a_note(pilot):
    W, t = _mutated(pilot, lambda W, t: t["driver_notes"][0].update(text="see H-01 for this"))
    assert validate.leaks(W, t)


def test_evidence_check_catches_a_rule_with_no_traces(pilot):
    W, t = _mutated(pilot, lambda W, t: [o.update(rule_id=None, status="delivered") for o in t["trip_outcomes"]
                                         if o.get("rule_id") == "H-16"])
    ev = validate.evidence(W, t, *PILOT)
    ev["H-16"].update(notes=0)
    assert any(p.startswith("H-16") for p in validate.evidence_problems(ev, W))


# ---------- the full 90-day world
@pytest.fixture(scope="module")
def full(cfg):
    return generate.generate(cfg, list(cfg["companies"]), str(cfg["period"]["start"]), str(cfg["period"]["end"]))


def test_full_world_is_clean(cfg, full):
    W, t = full
    problems, ev = generate.check(W, t, list(cfg["companies"]), str(cfg["period"]["start"]), str(cfg["period"]["end"]))
    assert problems == []


def test_every_planned_exposure_happens(cfg, full):
    W, t = full
    ev = validate.evidence(W, t, list(cfg["companies"]), str(cfg["period"]["start"]), str(cfg["period"]["end"]))
    for rid in ("H-01", "H-09", "H-16", "H-21"):
        assert ev[rid]["failures"] >= ev[rid]["planned_exposures_in_window"] - 1, rid
    assert ev["H-12"]["failures"] == 1 and ev["H-12"]["successes_long"] >= 3     # one false note, then successes


def test_full_world_rates_look_real(full):
    W, t = full
    for cid in ("T01", "T02", "T03"):
        orders = [o for o in t["orders"] if o["company"] == cid]
        assert sum(o["status"] == "rolled_over" for o in orders) / len(orders) < 0.06, cid
        outs = [o for o in t["trip_outcomes"] if o["company"] == cid]
        assert sum(o["status"] == "returned" for o in outs) / len(outs) < 0.03, cid
    langs = validate.stats(t)["languages"]
    assert langs["rt"] > langs["te"] > langs["en"]
