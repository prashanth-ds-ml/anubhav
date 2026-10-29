"""Layer 3 tests: the evidence gate on true rules and traps, the lesson lifecycle, use by the agent and validator,
challenge/expiry/rollback, and domain packs (eligibility, translation, leaks, opt-in, revocation). No Muse calls."""

import pytest

from anubhav.agent import graph
from anubhav.data import generate
from anubhav.learning import digest, gate, miner, pack, report
from anubhav.learning.store import LessonStore, ReviewError
from anubhav.muse import MockClient, mock_final
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("worlds")
    assert generate.main(["--full", "--out", str(out)]) == 0
    return next(out.iterdir())


@pytest.fixture
def C(world, tmp_path):
    return lambda company: CompanyData(world, company, tmp_path / "rt")


@pytest.fixture
def S(tmp_path):
    return LessonStore(tmp_path / "learning.sqlite")


def sid(C, name, town):
    return next(s for s, v in C.sites.items() if v["name"] == name and v["town"] == town)


def truth_and_traps(c):
    LAK, SVT, VST = sid(c, "Lakshmi Agencies", "Jangaon"), sid(c, "Sri Venkateswara Traders", "Jangaon"), sid(c, "Venkata Sri Traders", "Warangal")
    GNS, SRW, SLN = sid(c, "Ganesh Stores", "Mahabubabad"), sid(c, "Sri Rama Warehousing", "Jangaon"), sid(c, "Sri Lakshmi Narasimha Traders", "Parkal")
    true = {"H-01": {"kind": "site_access", "params": {"site_id": LAK, "max_length_ft": 22}},
            "H-03": {"kind": "alias", "params": {"phrase": "Pedda godown", "target_kind": "site", "target_id": VST}},
            "H-05": {"kind": "alias", "params": {"phrase": "nalla lorry", "target_kind": "vehicle", "target_id": "V11"}},
            "H-06": {"kind": "alias", "params": {"phrase": "Anna vallu", "target_kind": "vendor", "target_id": "SVR Transport"}},
            "H-14": {"kind": "real_capacity", "params": {"vehicle_id": "V13", "max_kg": 12000}},
            "H-15": {"kind": "vendor_reliability", "params": {"vendor": "Sri Durga Roadlines", "condition": "month_end"}},
            "H-16": {"kind": "weekly_off", "params": {"site_id": SLN, "weekday": 1}},
            "H-18": {"kind": "night_only", "params": {"site_id": SRW, "from_hour": 22, "to_hour": 6}}}
    traps = {"H-08 habit": {"kind": "vehicle_requirement", "params": {"town": "Khammam", "vehicle_class": "T32M"}},
             "H-12 wrong note": {"kind": "site_access", "params": {"site_id": GNS, "max_length_ft": 22}},
             "H-02 look-alike": {"kind": "site_access", "params": {"site_id": SVT, "max_length_ft": 22}},
             "town-wide": {"kind": "site_access", "params": {"town": "Jangaon", "max_length_ft": 22}},
             "wrong alias": {"kind": "alias", "params": {"phrase": "Pedda godown", "target_kind": "site", "target_id": LAK}},
             "unsupported": {"kind": "other", "params": {"description": "ice boxes are enough for dairy"}}}
    return true, traps


# ---------- the gate
def test_gate_keeps_true_rules_and_rejects_every_trap(C):
    c = C("T01")
    F = digest.Facts(c)
    true, traps = truth_and_traps(c)
    for name, les in true.items():
        assert gate.check(F, les)["verdict"] == "candidate", name
    for name, les in traps.items():
        assert gate.check(F, les)["verdict"] == "rejected", name
    assert gate.check(F, {"kind": "closure", "params": {"town": "Kazipet", "what": "bridge"}})["verdict"] == "expired"


def test_gate_is_conservative_about_single_evidence(C):
    c = C("T01")
    F = digest.Facts(c)
    les = truth_and_traps(c)[0]["H-01"]
    one = digest.Facts(c)
    first = next(x for x in one.by_site[les["params"]["site_id"]] if x["status"] == "returned")
    one.by_site[les["params"]["site_id"]] = [x for x in one.by_site[les["params"]["site_id"]] if x["status"] != "returned"] + [first]
    assert gate.check(one, les)["verdict"] == "needs_evidence"
    assert gate.check(F, les)["enforceable"] is True


def test_miner_parse_is_robust():
    assert miner.parse("no json here") == []
    assert miner.parse('blah {"lessons": [{"kind": "alias"}]} trailing') == [{"kind": "alias"}]
    assert miner.parse('{"lessons": [broken') == []


def test_digest_contains_only_visible_records(C):
    _, d = digest.build(C("T01"))
    text = "\n".join(d.values())
    for hidden in ("true_cause", "rule_id", "H-01", "site_key", "real_payload"):
        assert hidden not in text


# ---------- lifecycle
def test_lifecycle_and_review_rules(C, S):
    c = C("T01")
    F = digest.Facts(c)
    true, traps = truth_and_traps(c)
    ids = S.add_proposals("T01", F, [true["H-01"], true["H-03"], traps["H-08 habit"]])
    l1, l3, l8 = (S.get(i) for i in ids)
    assert (l1["state"], l3["state"], l8["state"]) == ("CANDIDATE", "CANDIDATE", "REJECTED")
    with pytest.raises(ReviewError):
        S.approve(l8["lesson_id"], "rev")                                  # rejected by the gate: can't approve
    with pytest.raises(ReviewError):
        S.approve(l3["lesson_id"], "rev", "policy", "x")                    # aliases aren't enforceable
    with pytest.raises(ReviewError):
        S.approve(l1["lesson_id"], "rev", "policy", "")                     # a policy must say what was verified
    assert S.approve(l1["lesson_id"], "rev", "policy", "3 refused trips; gate measured")["state"] == "ACTIVE_POLICY"
    assert S.rollback(l1["lesson_id"], "rev")["state"] == "CANDIDATE"
    assert [e["action"] for e in S.events(l1["lesson_id"])] == ["propose", "approve_policy", "rollback"]


def test_active_lessons_reach_the_agent_and_the_validator(C, S, tmp_path):
    c = C("T01")
    F = digest.Facts(c)
    true, _ = truth_and_traps(c)
    a, b = S.add_proposals("T01", F, [true["H-01"], true["H-03"]])
    S.approve(a, "rev", "policy", "3 refused trips")
    S.approve(b, "rev")
    knowledge, policies, advisories = S.active_for("T01", c)
    assert any("Pedda godown" in k for k in knowledge) and policies[0]["max_length_ft"] == 22
    br = Broker(c, Session("T01"), policies, advisories)
    order = next(o for o in br.call("list_open_orders", {})["result"]["orders"] if o["site"] == "Lakshmi Agencies")
    t32 = next(v for v in br.call("list_vehicles", {"status": "available"})["result"]["vehicles"]
               if v["length_ft"] == 32 and v["payload_kg"] >= order["kg"]
               and min(v[k] for k in ("fitness_until", "permit_until", "insurance_until", "puc_until")) >= c.today)
    r = br.call("create_dispatch_draft", {"order_ids": [order["order_id"]], "vehicle_id": t32["vehicle_id"]})
    assert r["error"]["code"] == "SITE_ACCESS"
    seen = {}
    def step(msgs, tools):
        seen["system"] = msgs[0]["content"]
        return mock_final("ok")
    graph.run(br, MockClient([step]), "Pedda godown load ki bandi pettu", knowledge=knowledge)
    assert "Pedda godown" in seen["system"] and "approved rule" in seen["system"]


def test_new_contradicting_evidence_challenges_a_lesson(C, S):
    c = C("T01")
    F = digest.Facts(c)
    les = truth_and_traps(c)[0]["H-01"]
    (lid,) = S.add_proposals("T01", F, [les])
    S.approve(lid, "rev", "policy", "3 refused trips")
    site = les["params"]["site_id"]
    ok = dict(F.by_site[site][0], status="delivered", length_ft=32, arrived="2026-10-29T09:00", status_seen=None)
    F.by_site[site].append(ok)                                               # e.g. the lane was widened
    changed = S.recheck("T01", F)
    assert changed[0]["state"] == "CHALLENGED"
    assert S.active_for("T01", c)[1] == []                                   # no longer enforced


# ---------- domain packs
def test_pack_shares_only_regional_lessons_in_the_recipients_ids(C, S):
    src, dst = C("T01"), C("TNEW")
    F = digest.Facts(src)
    true, _ = truth_and_traps(src)
    ids = S.add_proposals("T01", F, list(true.values()))
    for i in ids:
        les = S.get(i)
        S.approve(i, "rev", "policy" if les["gate"].get("enforceable") else "advisory", "measured")
    p = pack.publish(S, src, dst, approved_by="owner-T01")
    kinds = {(it["kind"], it["params"].get("target_kind")) for it in p["items"]}
    assert ("site_access", None) in kinds and ("alias", "site") in kinds
    assert not {k for k, _ in kinds} & {"real_capacity", "vendor_reliability"} and ("alias", "vehicle") not in kinds
    assert pack.leaks(p, src) == []
    lak_new = sid(dst, "Lakshmi Agencies", "Jangaon")
    assert any(it["params"].get("site_id") == lak_new for it in p["items"])
    new_ids = pack.import_pack(S, p, dst, accepted_by="owner-TNEW", accept_policies=True)
    _, policies, _ = S.active_for("TNEW", dst)
    assert policies and policies[0]["site_id"] == lak_new
    pack.revoke(S, p["pack_id"], "TNEW", "owner-T01")
    assert S.active_for("TNEW", dst)[1] == [] and all(S.get(i)["state"] == "RETIRED" for i in new_ids)


def test_pack_needs_approval_and_refuses_leaks(C, S):
    src, dst = C("T01"), C("TNEW")
    F = digest.Facts(src)
    with pytest.raises(PermissionError):
        pack.publish(S, src, dst, approved_by="")
    vst = sid(src, "Venkata Sri Traders", "Warangal")
    (lid,) = S.add_proposals("T01", F, [{"kind": "alias", "params": {"phrase": "Pedda godown", "target_kind": "site", "target_id": vst}}])
    S.approve(lid, "rev")
    with S._con() as con:                                          # a sloppy phrase that names a private truck
        con.execute("update lessons set params = ? where lesson_id = ?",
                    ('{"phrase": "V11 godown", "target_kind": "site", "target_id": "%s"}' % vst, lid))
    with pytest.raises(PermissionError, match="leak"):
        pack.publish(S, src, dst, approved_by="owner")
    with pytest.raises(PermissionError):
        pack.import_pack(S, {"pack_id": "x", "items": []}, dst, accepted_by="")


def test_report_explains_decisions(C, S):
    c = C("T01")
    F = digest.Facts(c)
    true, traps = truth_and_traps(c)
    ids = S.add_proposals("T01", F, [true["H-01"], traps["H-08 habit"]])
    S.approve(ids[0], "rev", "policy", "3 refused trips")
    text = report.weekly(S, "T01", c)
    assert "Approved and in use" in text and "Rejected (and why)" in text and "habit, not a rule" in text


def test_learning_curve_replays_the_gate_day_by_day(C, S):
    from anubhav.learning import timeline
    c = C("T01")
    true, _ = truth_and_traps(c)
    S.add_proposals("T01", digest.Facts(c), [true["H-01"], true["H-14"]])
    rows = {r["kind"]: r for r in timeline.curve(c, S.list("T01"), "2026-08-01", "2026-10-29")}
    j = rows["site_access"]
    assert j["first_seen"] == "2026-08-19" and j["learnable"] == "2026-08-20" and j["incidents_after"] == 1
    assert rows["real_capacity"]["learnable"] < j["learnable"] and rows["real_capacity"]["incidents_after"] > 10


def test_facts_cutoff_hides_later_records(C):
    c = C("T01")
    early, full = digest.Facts(c, until="2026-08-10"), digest.Facts(c)
    assert len(early.visits) < len(full.visits) and all(v["date"] <= "2026-08-10" for v in early.visits)
    assert early.today == "2026-08-10"


def test_relearning_adds_only_new_findings(C, S):
    c = C("T01")
    F = digest.Facts(c)
    true, traps = truth_and_traps(c)
    first = S.add_proposals("T01", F, [true["H-01"], true["H-03"]])
    again = S.add_proposals("T01", F, [true["H-01"], true["H-03"], traps["H-08 habit"]])
    assert len(first) == 2 and len(again) == 1 and len(S.list("T01")) == 3


# ---------- EXP-009 gate refinements
def test_vendor_claims_need_statistical_significance():
    assert gate.fisher_greater(3, 9, 0, 36) < 0.01            # 3/9 vs 0/36: real
    assert gate.fisher_greater(9, 46, 5, 65) > 0.05           # 9/46 vs 5/65: could be luck
    assert gate.fisher_greater(2, 26, 4, 60) > 0.5


def test_closing_hour_must_match_where_the_evidence_starts(C):
    c = C("T01")
    F = digest.Facts(c)
    sid = next(iter(F.by_site))
    base = dict(F.by_site[sid][0], status="delivered", status_seen=None)
    F.by_site[sid] = [dict(base, hour=21, wait_min=600, arrived="2026-09-01T21:00"),
                      dict(base, hour=22, wait_min=560, arrived="2026-09-02T22:00")]
    assert gate.check(F, {"kind": "receiving_hours", "params": {"site_id": sid, "until_hour": 18}})["verdict"] == "rejected"
    assert gate.check(F, {"kind": "receiving_hours", "params": {"site_id": sid, "until_hour": 21}})["verdict"] == "candidate"


def test_vehicle_type_names_are_not_nicknames(C):
    c = C("T01")
    F = digest.Facts(c)
    v = next(v for v in c.vehicles.values() if v["class"] == "T32S" and v["owner"] != "spot")
    r = gate.check(F, {"kind": "alias", "params": {"phrase": "32 SXL bandi", "target_kind": "vehicle", "target_id": v["vehicle_id"]}})
    assert r["verdict"] == "rejected" and "type name" in r["reason"]


def test_same_lesson_from_two_partners_is_merged_and_revocation_respects_the_other(C, S):
    src, dst = C("T01"), C("TNEW")
    lak = sid(src, "Lakshmi Agencies", "Jangaon")
    (lid,) = S.add_proposals("T01", digest.Facts(src), [{"kind": "site_access", "params": {"site_id": lak, "max_length_ft": 22}}])
    S.approve(lid, "rev", "policy", "measured")
    p1 = pack.publish(S, src, dst, "owner")
    p2 = dict(p1, pack_id=p1["pack_id"] + "-B")                 # the same lesson arriving from a second partner
    a = pack.import_pack(S, p1, dst, "new-owner", True)
    b = pack.import_pack(S, p2, dst, "new-owner", True)
    assert a == b and len(S.list("TNEW")) == 1
    assert len(S.get(a[0])["gate"]["confirmed_by"]) == 2
    pack.revoke(S, p1["pack_id"], "TNEW", "owner")
    assert S.get(a[0])["state"] == "ACTIVE_POLICY"               # still confirmed by the other partner
    pack.revoke(S, p2["pack_id"], "TNEW", "owner")
    assert S.get(a[0])["state"] == "RETIRED"


def test_aliases_already_in_master_data_are_not_new_knowledge(C):
    c = C("T01")
    F = digest.Facts(c)
    v = next(v for v in c.vehicles.values() if v["owner"] != "spot")
    r = gate.check(F, {"kind": "alias", "params": {"phrase": v["reg_no"], "target_kind": "vehicle", "target_id": v["vehicle_id"]}})
    assert r["verdict"] == "rejected" and "already recorded" in r["reason"]


def test_leak_check_ignores_the_recipients_own_ids_but_not_the_sources(C, S):
    src, dst = C("T01"), C("TNEW")
    fake = {"items": [{"kind": "site_access", "params": {"site_id": next(iter(dst.sites))}}]}
    assert next(iter(dst.sites)) not in pack.leaks(fake, src, dst)
    v = next(v for v in src.vehicles.values() if v["owner"] != "own")
    bad = {"items": [{"kind": "alias", "params": {"phrase": v["reg_no"]}}]}
    assert v["reg_no"] in pack.leaks(bad, src, dst)
