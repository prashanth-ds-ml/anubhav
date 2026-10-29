"""Loop A store: harness versions and feedback. The harness is how the agent works (response guidelines, per-tool
hints, a language glossary), shared by every client. It never holds business facts (those are lessons, Loop B),
never touches permissions, the validator, data or model weights, and every version can be rolled back."""

import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

SURFACES = ("response_guidelines", "tool_hints", "glossary")
LIMITS = {"response_guidelines": 10, "glossary": 30, "line_chars": 260, "tool_hint_chars": 320}
EMPTY = {"response_guidelines": [], "tool_hints": {}, "glossary": []}
CATEGORIES = {"not_from_data": "Not from the data / not needed", "language": "Language or tone",
              "wrong_plan": "Wrong plan", "wrong_tool": "Used tools badly", "other": "Other"}


class PatchError(Exception):
    pass


def validate_patch(patch, tool_names, C=None):
    """Only allowed surfaces, small edits, and no business facts (site names, towns, vehicle ids, vendors)."""
    surface, op, text = patch.get("surface"), patch.get("op"), str(patch.get("text") or "").strip()
    if surface not in SURFACES:
        raise PatchError(f"surface '{surface}' can't be patched (allowed: {', '.join(SURFACES)})")
    if op not in ("add", "replace", "remove"):
        raise PatchError(f"op '{op}' not allowed")
    if surface == "tool_hints" and patch.get("tool") not in tool_names:
        raise PatchError(f"unknown tool '{patch.get('tool')}'")
    if op != "remove" and not text:
        raise PatchError("empty patch text")
    limit = LIMITS["tool_hint_chars"] if surface == "tool_hints" else LIMITS["line_chars"]
    if len(text) > limit:
        raise PatchError(f"patch text too long ({len(text)} > {limit} chars)")
    if re.search(r"(ignore|override|bypass).{0,30}(rule|validator|permission|safety|instruction)", text, re.I):
        raise PatchError("a harness patch can't weaken safety, permissions or the validator")
    if C is not None:
        facts = {s["name"].lower() for s in C.sites.values()} | {s["town"].lower() for s in C.sites.values()}
        facts |= {v["vehicle_id"].lower() for v in C.vehicles.values()} | {v["vendor"].lower() for v in C.vehicles.values()}
        hit = sorted(f for f in facts if len(f) >= 4 and re.search(rf"(?<![a-z0-9]){re.escape(f)}(?![a-z0-9])", text.lower()))
        if hit:
            raise PatchError(f"business facts belong in lessons, not the harness: {hit[:3]}")


def apply_patch(surfaces, patch):
    s = json.loads(json.dumps(surfaces))
    surface, op, text = patch["surface"], patch["op"], str(patch.get("text") or "").strip()
    if surface == "tool_hints":
        if op == "remove":
            s["tool_hints"].pop(patch["tool"], None)
        else:
            s["tool_hints"][patch["tool"]] = text
    else:
        lst = s[surface]
        if op == "remove":
            s[surface] = [x for x in lst if x != patch.get("old", text)]
        elif op == "replace" and patch.get("old") in lst:
            lst[lst.index(patch["old"])] = text
        elif text not in lst:
            lst.append(text)
        if len(s[surface]) > LIMITS[surface]:
            raise PatchError(f"too many {surface} (max {LIMITS[surface]})")
    return s


def render(surfaces):
    """The text added to the agent's system prompt for this harness version."""
    parts = []
    if surfaces.get("response_guidelines"):
        parts.append("Working guidelines learned from feedback and tested:\n" + "\n".join(f"- {g}" for g in surfaces["response_guidelines"]))
    if surfaces.get("glossary"):
        parts.append("Language notes (from native speakers):\n" + "\n".join(f"- {g}" for g in surfaces["glossary"]))
    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def diff(old, new):
    out = []
    for k in ("response_guidelines", "glossary"):
        out += [f"+ {k}: {x}" for x in new.get(k, []) if x not in old.get(k, [])]
        out += [f"- {k}: {x}" for x in old.get(k, []) if x not in new.get(k, [])]
    for t in sorted(set(old.get("tool_hints", {})) | set(new.get("tool_hints", {}))):
        a, b = old.get("tool_hints", {}).get(t), new.get("tool_hints", {}).get(t)
        if a != b:
            out += ([f"- tool_hints[{t}]: {a}"] if a else []) + ([f"+ tool_hints[{t}]: {b}"] if b else [])
    return out


class HarnessStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.executescript("""
                create table if not exists versions (version_id text primary key, parent text, surfaces text, status text,
                    created text, patch text, rationale text, probe text, decided_by text, decided text, note text);
                create table if not exists practice (ts text, round text, version_id text, split text, company text,
                    qid text, qtype text, lang text, question text, tools text, used_tool int, right_tool int,
                    tool_errors int, answer_ok int, cost_usd real, reply text, run_id text);
                create table if not exists feedback (feedback_id text primary key, ts text, company text, run_id text,
                    request text, reply text, rating int, category text, note text, source text, status text,
                    use_lessons int);
            """)
            if not con.execute("select 1 from versions").fetchone():
                con.execute("insert into versions values (?,?,?,?,?,?,?,?,?,?,?)",
                            ("h-000", None, json.dumps(EMPTY), "active", _now(), None, "baseline", None, "system", _now(), ""))

    def _con(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _row(self, r):
        d = dict(r)
        for k in ("surfaces", "patch", "probe"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        return d

    # ---------- versions
    def active(self):
        with self._con() as con:
            return self._row(con.execute("select * from versions where status = 'active'").fetchone())

    def get(self, vid):
        with self._con() as con:
            r = con.execute("select * from versions where version_id = ?", (vid,)).fetchone()
            return self._row(r) if r else None

    def versions(self):
        with self._con() as con:
            return [self._row(r) for r in con.execute("select * from versions order by created")]

    def propose(self, patch, rationale, tool_names, C=None):
        validate_patch(patch, tool_names, C)
        base = self.active()
        surfaces = apply_patch(base["surfaces"], patch)
        with self._con() as con:
            n = con.execute("select count(*) from versions").fetchone()[0]
            vid = f"h-{n:03d}"
            con.execute("insert into versions values (?,?,?,?,?,?,?,?,?,?,?)",
                        (vid, base["version_id"], json.dumps(surfaces, ensure_ascii=False), "candidate", _now(),
                         json.dumps(patch, ensure_ascii=False), rationale, None, None, None, ""))
        return self.get(vid)

    def record_probe(self, vid, result):
        with self._con() as con:
            con.execute("update versions set probe = ? where version_id = ?", (json.dumps(result, ensure_ascii=False, default=str), vid))

    def decide(self, vid, by, approve, note=""):
        v = self.get(vid)
        if v["status"] != "candidate":
            raise PatchError(f"{vid} is {v['status']}")
        if approve and not (v["probe"] or {}).get("gate", {}).get("pass"):
            raise PatchError("only a candidate that passed its paired test can be activated")
        with self._con() as con:
            if approve:
                con.execute("update versions set status = 'superseded' where status = 'active'")
            con.execute("update versions set status = ?, decided_by = ?, decided = ?, note = ? where version_id = ?",
                        ("active" if approve else "rejected", by, _now(), note, vid))
        return self.get(vid)

    def rollback(self, by):
        cur = self.active()
        if not cur["parent"]:
            raise PatchError("already at the baseline")
        with self._con() as con:
            con.execute("update versions set status = 'rolled_back', decided_by = ?, decided = ? where version_id = ?",
                        (by, _now(), cur["version_id"]))
            con.execute("update versions set status = 'active' where version_id = ?", (cur["parent"],))
        return self.active()

    # ---------- practice results (the Skills view reads these)
    def add_practice(self, round_id, version_id, results):
        with self._con() as con:
            con.executemany("insert into practice values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (_now(), round_id, version_id, x["split"], x["company"], x["id"], x["type"], x["lang"], x["question"],
                 json.dumps(x["tools"]), int(x["used_tool"]), int(x["right_tool"]), x["tool_errors"], int(x["answer_ok"]),
                 x["cost_usd"], x["reply"], x["run_id"]) for x in results])

    def practice(self):
        with self._con() as con:
            return [dict(r) for r in con.execute("select * from practice order by ts")]

    # ---------- feedback
    def add_feedback(self, company, run, rating, category, note, source="tester"):
        fid = f"FB-{uuid.uuid4().hex[:6].upper()}"
        with self._con() as con:
            con.execute("insert into feedback values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (fid, _now(), company, run.get("run_id"), run.get("request"), run.get("reply"), rating,
                         category, note, source, "new", int(bool(run.get("knowledge")))))
        return fid

    def feedback(self, status=None):
        with self._con() as con:
            rows = [dict(r) for r in con.execute("select * from feedback order by ts")]
        return [r for r in rows if not status or r["status"] == status]

    def mark_feedback(self, ids, status):
        with self._con() as con:
            con.executemany("update feedback set status = ? where feedback_id = ?", [(status, i) for i in ids])


def _now():
    return datetime.now().isoformat(timespec="seconds")
