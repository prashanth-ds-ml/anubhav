"""Typed events (D-044, design v1 §4.5): one stream per request that says which agent acted, what it called, what came
back, where it retried, when no tool fitted, who handed what to whom, which lessons and checks were involved, and which
drafts were made. Built from a saved run (live or replay, single-Planner or team), stored in SQLite, read the same way
by the live stream and the history. The schema is contracts/events.schema.json.

An event is {run_id, seq, agent_id, caller, depth, ts, type, payload}; run_id is the request's (the lead agent's) id."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .data.config import ROOT

PATH = ROOT / "data" / "events.sqlite"
TYPES = ("agent_start", "tool_call", "tool_result", "retry", "tool_missing", "handoff", "lesson_used",
         "validator_check", "draft_created", "agent_done", "learning_event")
DRAFT_TOOLS = ("create_dispatch_draft", "create_dispatch_drafts", "check_load")
LESSON_KEYS = ("approved_policies", "advisories", "approved_rules", "advice")


def _short(x, n=600):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


def _lessons_in(result):
    """Approved lessons a tool result carried (site rules and advice), found anywhere in it."""
    found = []
    if isinstance(result, dict):
        for k, v in result.items():
            if k in LESSON_KEYS and v:
                found += v if isinstance(v, list) else [v]
            else:
                found += _lessons_in(v)
    elif isinstance(result, list):
        for v in result:
            found += _lessons_in(v)
    return found


def from_run(run: dict) -> list[dict]:
    """All events of one request: the lead's run and, nested in place, each teammate run it delegated to."""
    children = {c["run_id"]: c for c in run.get("children", [])}
    events = []

    def emit(r, caller, depth, type_, payload):
        events.append({"run_id": run["run_id"], "seq": len(events), "agent_id": r.get("agent_id") or "planner",
                       "agent_run_id": r["run_id"], "caller": caller, "depth": depth, "ts": run.get("saved_at"),
                       "type": type_, "payload": payload})

    def walk(r, caller, depth):
        emit(r, caller, depth, "agent_start", {"request": r["request"], "model": r.get("model"),
                                               "lessons_in_prompt": len(r.get("knowledge") or [])})
        for s in r["trace"]:
            if s["type"] == "tool":
                args = s.get("arguments")
                args = json.loads(args) if isinstance(args, str) and args.strip().startswith("{") else args
                if s.get("attempt", 1) > 1:
                    emit(r, caller, depth, "retry", {"tool": s["name"], "attempt": s["attempt"], "of": 3})
                emit(r, caller, depth, "tool_call", {"tool": s["name"], "arguments": args})
                res = s.get("result") or {}
                if s["name"] == "delegate" and s["ok"]:
                    emit(r, caller, depth, "handoff", {"from": r.get("agent_id") or "planner", "to": res.get("agent"),
                                                       "brief": (args or {}).get("brief", "")})
                    if res.get("run_id") in children:
                        walk(children[res["run_id"]], r.get("agent_id") or "planner", depth + 1)
                emit(r, caller, depth, "tool_result", {"tool": s["name"], "ok": s["ok"],
                                                       **({"result": _short(res)} if s["ok"] else {"error": s.get("error")})})
                if s["name"] == "find_capability" and s["ok"] and res.get("tool_missing"):
                    emit(r, caller, depth, "tool_missing", {"need": res.get("need"), "next_step": res.get("next_step")})
                if s["ok"]:
                    lessons = _lessons_in(res)
                    if lessons:
                        emit(r, caller, depth, "lesson_used", {"tool": s["name"], "lessons": lessons[:10]})
                if s["name"] in DRAFT_TOOLS:
                    if not s["ok"]:
                        emit(r, caller, depth, "validator_check", {"tool": s["name"], "pass": False, "error": s.get("error")})
                    elif s["name"] == "check_load":
                        emit(r, caller, depth, "validator_check", {"tool": s["name"], "pass": bool(res.get("all_ok")),
                                                                    "checked": len(res.get("checked", []))})
                    else:
                        made = [res] if s["name"] == "create_dispatch_draft" else res.get("results", [])
                        for d in made:
                            if d.get("draft_id"):
                                emit(r, caller, depth, "validator_check", {"tool": s["name"], "pass": True, "draft_id": d["draft_id"]})
                                emit(r, caller, depth, "draft_created", {"draft_id": d["draft_id"], "vehicle_id": d.get("vehicle_id"),
                                                                          "orders": d.get("orders"), "load": d.get("load")})
                            else:
                                emit(r, caller, depth, "validator_check", {"tool": s["name"], "pass": False, "error": d.get("error") or d.get("errors")})
            elif s["type"] == "finish":
                for c in s.get("draft_checks", []):
                    emit(r, caller, depth, "validator_check", {"tool": "final_recheck", "pass": c["still_valid"],
                                                                "draft_id": c["draft_id"], "errors": c["errors"]})
        emit(r, caller, depth, "agent_done", {"reply": r.get("reply", ""), "stop": r.get("stop"), "cost_usd": r.get("cost_usd"),
                                              "tool_calls": r.get("tool_calls"), "drafts": r.get("drafts", []),
                                              "reply_check": r.get("reply_check")})

    walk(run, run.get("caller") or "person", run.get("depth", 0))
    return events


class EventStore:
    def __init__(self, path: Path = PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.execute("create table if not exists events (run_id text, seq int, agent_id text, agent_run_id text, "
                        "caller text, depth int, ts text, type text, payload text, primary key (run_id, seq))")

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.path)        # closed every time (Windows keeps open files locked)
        try:
            with con:
                yield con
        finally:
            con.close()

    def save(self, events):
        with self._con() as con:
            con.executemany("insert or replace into events values (?,?,?,?,?,?,?,?,?)",
                            [(e["run_id"], e["seq"], e["agent_id"], e["agent_run_id"], e["caller"], e["depth"], e["ts"],
                              e["type"], json.dumps(e["payload"], ensure_ascii=False, default=str)) for e in events])

    def add_run(self, run):
        ev = from_run(run)
        self.save(ev)
        return ev

    def load(self, run_id, after=-1):
        """A request's events in order; `after` lets a reconnecting stream fetch only what it missed."""
        cols = ("run_id", "seq", "agent_id", "agent_run_id", "caller", "depth", "ts", "type", "payload")
        with self._con() as con:
            rows = con.execute("select * from events where run_id = ? and seq > ? order by seq", (run_id, after)).fetchall()
        return [dict(zip(cols, r[:-1]), payload=json.loads(r[-1])) for r in rows]

    def runs(self):
        with self._con() as con:
            return [r[0] for r in con.execute("select distinct run_id from events order by rowid desc")]
