"""The lesson store and its lifecycle (PRD v3.1 §9.2). Every lesson is bound to one company. Every state change is
an append-only event, so any approval can be audited and rolled back.

States: CANDIDATE / NEEDS_EVIDENCE (from the gate) -> ACTIVE_ADVISORY / ACTIVE_POLICY (reviewer) -> CHALLENGED
(new contradicting evidence) -> RETIRED. Also REJECTED (gate or reviewer) and EXPIRED (time-bound and over)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import gate as G

GATE_STATE = {"candidate": "CANDIDATE", "needs_evidence": "NEEDS_EVIDENCE", "rejected": "REJECTED", "expired": "EXPIRED"}
ACTIVE = {"ACTIVE_ADVISORY", "ACTIVE_POLICY"}


class ReviewError(Exception):
    pass


class LessonStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.executescript("""
                create table if not exists lessons (lesson_id text primary key, company text, kind text, params text,
                    claim text, state text, effect text, gate text, miner text, source text, created text, updated text,
                    reviewer text, verified text, valid_from text, valid_to text);
                create table if not exists lesson_events (ts text, lesson_id text, company text, actor text, action text,
                    from_state text, to_state text, note text);
            """)

    def _con(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _row(self, r):
        d = dict(r)
        for k in ("params", "gate", "miner"):
            d[k] = json.loads(d[k]) if d[k] else None
        return d

    def _event(self, con, lid, company, actor, action, a, b, note=""):
        con.execute("insert into lesson_events values (?,?,?,?,?,?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), lid, company, actor, action, a, b, note))

    # ---------- adding proposals (always through the gate)
    def add_proposals(self, company, F, proposals, miner_meta=None, source="mined"):
        out = []
        with self._con() as con:
            n = con.execute("select count(*) from lessons where company = ?", (company,)).fetchone()[0]
            for p in proposals:
                g = G.check(F, p)
                n += 1
                lid = f"L-{company}-{n:03d}"
                now = datetime.now().isoformat(timespec="seconds")
                state = GATE_STATE[g["verdict"]]
                con.execute("insert into lessons values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (lid, company, p.get("kind"), json.dumps(p.get("params") or {}, ensure_ascii=False),
                             p.get("claim", ""), state, None, json.dumps(g, ensure_ascii=False),
                             json.dumps({k: p.get(k) for k in ("evidence", "counter_evidence", "alternatives", "confidence")}
                                        | (miner_meta or {}), ensure_ascii=False), source, now, now, None, None,
                             g.get("valid_from"), g.get("valid_to")))
                self._event(con, lid, company, "gate", "propose", None, state, g["reason"])
                out.append(lid)
        return out

    # ---------- reading
    def get(self, lid):
        with self._con() as con:
            r = con.execute("select * from lessons where lesson_id = ?", (lid,)).fetchone()
            return self._row(r) if r else None

    def list(self, company, states=None):
        with self._con() as con:
            rows = [self._row(r) for r in con.execute("select * from lessons where company = ? order by lesson_id", (company,))]
        return [r for r in rows if not states or r["state"] in states]

    def events(self, lid=None, company=None):
        with self._con() as con:
            if lid:
                return [dict(r) for r in con.execute("select * from lesson_events where lesson_id = ? order by rowid", (lid,))]
            return [dict(r) for r in con.execute("select * from lesson_events where company = ? order by rowid", (company,))]

    # ---------- reviewer actions (each one checked and logged)
    def _move(self, lid, actor, action, to_state, note="", **fields):
        with self._con() as con:
            r = con.execute("select * from lessons where lesson_id = ?", (lid,)).fetchone()
            if not r:
                raise ReviewError(f"no lesson {lid}")
            sets = ", ".join(f"{k} = ?" for k in ["state", "updated", *fields])
            con.execute(f"update lessons set {sets} where lesson_id = ?",
                        (to_state, datetime.now().isoformat(timespec="seconds"), *fields.values(), lid))
            self._event(con, lid, r["company"], actor, action, r["state"], to_state, note)
        return self.get(lid)

    def approve(self, lid, reviewer, effect="advisory", verified=""):
        les = self.get(lid)
        if les["state"] not in ("CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED"):
            raise ReviewError(f"{lid} is {les['state']}; only gate-passed lessons can be approved")
        if effect == "policy":
            if les["state"] != "CANDIDATE" or not (les["gate"] or {}).get("enforceable"):
                raise ReviewError(f"{lid} can't be a policy: needs repeated evidence and an enforceable kind (one failure is advice only)")
            if not verified.strip():
                raise ReviewError("a policy needs the reviewer to say what was verified (site visit, operator, repeated failures)")
        state = "ACTIVE_POLICY" if effect == "policy" else "ACTIVE_ADVISORY"
        return self._move(lid, reviewer, f"approve_{effect}", state, verified, effect=effect, reviewer=reviewer, verified=verified)

    def reject(self, lid, reviewer, why):
        return self._move(lid, reviewer, "reject", "REJECTED", why, reviewer=reviewer)

    def retire(self, lid, reviewer, why):
        return self._move(lid, reviewer, "retire", "RETIRED", why)

    def rollback(self, lid, actor):
        """Undo the last state change (the full history stays in lesson_events)."""
        ev = [e for e in self.events(lid) if e["action"] != "rollback"]
        if len(ev) < 2:
            raise ReviewError(f"{lid} has nothing to roll back")
        return self._move(lid, actor, "rollback", ev[-1]["from_state"], f"undo {ev[-1]['action']}")

    def recheck(self, company, F, actor="recheck"):
        """Re-run the gate on active lessons with the latest records; contradicted ones become CHALLENGED and
        stop being used until a reviewer decides. Time-bound ones that ended become EXPIRED."""
        changed = []
        for les in self.list(company, ACTIVE):
            g = G.check(F, {"kind": les["kind"], "params": les["params"]})
            if g["verdict"] == "rejected":
                changed.append(self._move(les["lesson_id"], actor, "challenge", "CHALLENGED", g["reason"]))
            elif g["verdict"] == "expired":
                changed.append(self._move(les["lesson_id"], actor, "expire", "EXPIRED", g["reason"]))
        return changed

    # ---------- use: what the agent and the validator receive
    def active_for(self, company, C):
        """Turn active lessons into (knowledge text for the agent, enforceable policies, advisories for drafts)."""
        knowledge, policies, advisories = [], [], []
        for les in self.list(company, ACTIVE):
            p, lid = les["params"], les["lesson_id"]
            k = les["kind"]
            site = C.sites.get(p.get("site_id") or p.get("target_id") or "", {})
            where = f"{site.get('name')}, {site.get('town')} (site {site.get('site_id')})" if site else ""
            tag = "approved rule" if les["state"] == "ACTIVE_POLICY" else "advice"
            text = {
                "site_access": f"{where}: vehicles longer than {p.get('max_length_ft')} ft cannot enter",
                "receiving_hours": f"{where}: does not receive after {p.get('until_hour')}:00; plan arrival earlier",
                "night_only": f"{where}: receives only at night ({p.get('from_hour')}:00-{p.get('to_hour')}:00)",
                "time_window": f"{where}: vehicles of {p.get('min_length_ft')} ft or longer can't unload {p.get('from_hour')}:00-{p.get('to_hour')}:00",
                "weekly_off": f"{where or p.get('town')}: closed on {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][int(p.get('weekday', 0))]}",
                "alias": f"\"{p.get('phrase')}\" means " + (where if p.get("target_kind") == "site" else
                                                           f"vehicle {p.get('target_id')}" if p.get("target_kind") == "vehicle"
                                                           else f"vendor {p.get('target_id')}"),
                "real_capacity": f"vehicle {p.get('vehicle_id')} safely carries at most {p.get('max_kg')} kg (less than its paper payload)",
                "vendor_reliability": f"vendor {p.get('vendor')} often fails to place trucks in the last week of the month; book a backup",
                "closure": f"{p.get('town')}: {p.get('what', 'road problem')} (from {les.get('valid_from')} to {les.get('valid_to')})",
                "moved_site": f"{where}: has moved to a new godown; the master address is out of date, confirm the address",
            }.get(k, les["claim"])
            knowledge.append(f"{text} [{tag} {lid}]")
            if k == "site_access" and les["state"] == "ACTIVE_POLICY":
                policies.append({"site_id": p["site_id"], "max_length_ft": int(p["max_length_ft"]), "id": lid,
                                 "evidence": les["gate"]["reason"]})
            elif k in ("site_access", "time_window", "receiving_hours", "night_only", "weekly_off", "moved_site") and site:
                advisories.append({"site_id": site["site_id"], "id": lid, "text": text.split(": ", 1)[-1]})
        return knowledge, policies, advisories
