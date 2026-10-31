"""Where a finished live run can be picked up again: its conversation, kept apart from the trace (which is what gets
shown and shared). A run that stopped for a person, hit a limit or failed resumes from here; a rejected plan goes back
to the run that made it. Each visitor only ever sees their own."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime

from .. import trace

RESUMABLE = {"needs_person", "limit", "error"}


def _con():
    trace.TRACE_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(trace.TRACE_DIR / "checkpoints.sqlite", timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("create table if not exists checkpoints (run_id text primary key, sid text, company text, request text, stop text, "
                "status text, handoff text, use_lessons int, team int, state text, saved_at text)")
    return con


def save(run, state, sid, use_lessons, team):
    with closing(_con()) as con, con:
        con.execute("insert or replace into checkpoints values (?,?,?,?,?,?,?,?,?,?,?)",
                    (run["run_id"], sid, run["company"], run["request"], run["stop"], "open", json.dumps(run.get("handoff"), ensure_ascii=False),
                     int(use_lessons), int(team), json.dumps(state, ensure_ascii=False, default=str), datetime.now().isoformat(timespec="seconds")))


def _row(r):
    return {**dict(r), "handoff": json.loads(r["handoff"]), "state": json.loads(r["state"]), "use_lessons": bool(r["use_lessons"]), "team": bool(r["team"])}


def get(run_id, sid):
    with closing(_con()) as con:
        r = con.execute("select * from checkpoints where run_id = ? and sid = ?", (run_id, sid)).fetchone()
    return _row(r) if r else None


def claim(run_id):
    """Take a checkpoint for one resume. False if someone already did: a double click can't start (and pay for) two runs."""
    with closing(_con()) as con, con:
        return con.execute("update checkpoints set status = 'resumed' where run_id = ? and status = 'open'", (run_id,)).rowcount == 1


def reopen(run_id):
    """The resumed run crashed before saving anything: the person can try again."""
    with closing(_con()) as con, con:
        con.execute("update checkpoints set status = 'open' where run_id = ?", (run_id,))


def waiting(sid, company):
    """Runs stopped for this person, newest first."""
    with closing(_con()) as con:
        rows = con.execute("select * from checkpoints where sid = ? and company = ? and stop = 'needs_person' and status = 'open' "
                           "order by saved_at desc, rowid desc", (sid, company)).fetchall()
    return [{"run_id": r["run_id"], "request": r["request"], "handoff": json.loads(r["handoff"]), "saved_at": r["saved_at"]} for r in rows]


def for_draft(sid, company, draft_id):
    """The newest run that made this draft."""
    with closing(_con()) as con:
        rows = con.execute("select * from checkpoints where sid = ? and company = ? order by saved_at desc, rowid desc", (sid, company)).fetchall()
    return next((_row(r) for r in rows if draft_id in json.loads(r["state"]).get("drafts", [])), None)
