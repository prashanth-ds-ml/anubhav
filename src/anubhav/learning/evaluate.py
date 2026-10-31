"""Scoring mined lessons against the hidden truth. Evaluation-only: the agent, miner and gate never import this.

A rule is LEARNABLE for a company if that company's own records carry its traces (failures, waits, offloads,
no-shows, or >= 2 alias mentions). A mined lesson MATCHES a rule if its kind and scope agree (tolerances below).
Traps are rules whose correct outcome is rejection (habit, wrong note, look-alike, one-off, shortcut)."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

TRAP_KINDS = {"habit", "contradiction", "look_alike", "one_off", "cold_chain"}


class Truth:
    def __init__(self, world: Path):
        world = Path(world)
        self.rules = {r["id"]: r for r in json.loads((world / "truth" / "hidden_rules.json").read_text(encoding="utf-8"))}
        con = sqlite3.connect(world / "truth" / "canonical.sqlite")
        con.row_factory = sqlite3.Row
        self.key = {(r["company"], r["site_id"]): r["site_key"] for r in con.execute("select company, site_id, site_key from true_site_profiles")}
        self.town = {(r["company"], r["site_id"]): r["town"] for r in con.execute("select company, site_id, town from sites")}
        self.traces = defaultdict(int)
        for table in ("trip_outcomes", "trip_events", "vehicle_placements"):
            for r in con.execute(f"select company, rule_id from {table} where rule_id is not null"):
                self.traces[(r["company"], r["rule_id"])] += 1
        self.mentions = defaultdict(int)
        for r in con.execute("select company, text from planner_messages"):
            for rid, rule in self.rules.items():
                if rule["kind"] == "alias" and r["company"] in rule["companies"] and rule["phrase"].lower() in r["text"].lower():
                    self.mentions[(r["company"], rid)] += 1
        con.close()

    def learnable(self, company):
        out = []
        for rid, r in self.rules.items():
            if r["kind"] in TRAP_KINDS or r["kind"] == "written_rule":
                continue
            if r["kind"] == "alias" and self.mentions[(company, rid)] >= 2 or self.traces[(company, rid)] >= 1:
                out.append(rid)
        return sorted(out)

    def traps(self, company):
        return sorted(rid for rid, r in self.rules.items() if r["kind"] in TRAP_KINDS
                      and (r.get("company") in (None, company)) and (r["kind"] != "look_alike" or self.traces[(company, rid)] >= 0))

    def match(self, company, les):
        """The hidden rule a lesson corresponds to (or None)."""
        k, p = les["kind"], les["params"] or {}
        key = self.key.get((company, p.get("site_id") or p.get("target_id")))
        for rid, r in self.rules.items():
            rk = r["kind"]
            if k == "site_access" and rk in ("site_access", "look_alike", "contradiction") and key == r.get("site"):
                if rk != "site_access" or r["max_length_ft"] - 4 <= int(p.get("max_length_ft", 0)) <= r["max_length_ft"]:
                    return rid
            if k == "alias" and rk == "alias" and company in r["companies"] and str(p.get("phrase", "")).lower().strip() in r["phrase"].lower() + " bandi":
                t = r["resolved"].get(company)
                if t and (t == p.get("target_id")):
                    return rid
            if k == "real_capacity" and rk == "real_capacity" and r.get("resolved", {}).get(company) == p.get("vehicle_id") \
                    and abs(float(p.get("max_kg", 0)) - r["real_payload_kg"]) <= 1000:
                return rid
            if k == "vendor_reliability" and rk == "vendor_reliability" and r["company"] == company and p.get("vendor") == r["vendor"]:
                return rid
            if k == "weekly_off" and rk == "weekly_off" and int(p.get("weekday", -1)) == r["weekday"] and \
                    (str(p.get("town", "")).lower() == r["town"].lower() or self.town.get((company, p.get("site_id"))) == r["town"]):
                return rid
            if k == "night_only" and rk == "night_only" and key == r["site"]:
                return rid
            if k == "receiving_hours" and rk == "receiving_hours" and key == r["site"] and abs(int(p.get("until_hour", 0)) - r["until_hour"]) <= 1:
                return rid
            if k == "time_window" and rk == "time_window" and key == r["site"]:
                return rid
            if k == "closure" and rk == "closure" and str(p.get("town", "")).lower() == r["town"].lower():
                return rid
            if k == "moved_site" and rk == "moved_godown" and key == r["site"]:
                return rid
            if k == "vehicle_requirement" and rk == "habit" and str(p.get("town", "")).lower() == r["town"].lower():
                return rid
        return None


def score(truth, company, lessons):
    """lessons: rows from LessonStore.list(company)."""
    learn = set(truth.learnable(company))
    passed = [l for l in lessons if l["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "EXPIRED")]
    rows, found, admitted_traps, false = [], set(), set(), []
    for l in lessons:
        rid = truth.match(company, l)
        ok = l["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "EXPIRED")
        kind = truth.rules[rid]["kind"] if rid else None
        rows.append({"lesson": l["lesson_id"], "kind": l["kind"], "state": l["state"], "matches": rid, "trap": kind in TRAP_KINDS})
        if ok and rid and kind not in TRAP_KINDS:
            found.add(rid)
        elif ok and rid and kind in TRAP_KINDS:
            admitted_traps.add(rid)
        elif ok and not rid:
            false.append(l["lesson_id"])
    true_passed = sum(1 for r in rows if r["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "EXPIRED") and r["matches"] and not r["trap"])
    return {"learnable": sorted(learn), "found": sorted(found & learn), "missed": sorted(learn - found),
            "precision": round(true_passed / len(passed), 3) if passed else None,
            "recall": round(len(found & learn) / len(learn), 3) if learn else None,
            "false_lessons": false, "traps_admitted": sorted(admitted_traps),
            "traps_proposed_and_rejected": sorted({r["matches"] for r in rows if r["trap"] and r["state"] == "REJECTED"}),
            "proposed": len(lessons), "passed": len(passed), "rows": rows}
