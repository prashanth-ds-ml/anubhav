"""Shared helpers for the Streamlit demo: one place that loads company data, the lesson store and saved traces,
runs the agent (live or replay), and turns a trace into something a person can read. Pages stay thin."""

import copy
import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

import streamlit as st

from .. import muse, trace
from ..agent import graph
from ..data.config import ROOT
from ..harness.store import HarnessStore
from ..learning import profile
from ..learning.store import LessonStore
from ..runtime.broker import Broker, Session
from ..runtime.company import CompanyData

WORLD = ROOT / "data" / "worlds" / "full_seed20261104"
EXP008 = sorted((ROOT / "artifacts" / "learning").glob("exp008_*_rep0.sqlite"))
DEMO = ROOT / "demo"            # git-tracked bundle for a fresh (hosted) checkout: saved real runs, EXP-008 lessons, practice
LIVE_RUNS_PER_SESSION = 8       # spend cap for live model calls on a public deployment
LIVE_CALLS_PER_DAY = 60         # and for the whole app, across every visitor and page (reloading doesn't reset it)
PUBLIC = os.environ.get("ANUBHAV_PUBLIC") == "1"   # hosted for judges: each visitor gets their own drafts and lessons
COMPANIES = {"T01": "Sri Kakatiya Logistics", "T02": "Ramappa Carriers", "T03": "Deccan Freight Services",
             "TNEW": "Bhadrakali Transport Co (new)"}
MODELS = {"Replay (free)": None, "Muse Spark Open": "open", "Muse Spark 1.3": "spark"}
SUGGESTIONS = {
    "Roman Telugu": "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku.",
    "Telugu": "రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు.",
    "English": "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.",
    "Mixed": "Jangaon Lakshmi order ki suitable vehicle choose chesi draft create cheyyi, confirm cheyyaku.",
    "Nickname": "Pedda godown load ki bandi pettu.",
    "Ambiguous": "Warangal load ki bandi pettu.",
}


@st.cache_resource
def ensure_world():
    """A fresh checkout has no data/ (git-ignored): generate the demo world from its seed. Deterministic, ~1 minute."""
    if not (WORLD / "manifest.json").exists():
        from ..data import generate
        generate.main(["--full"])
    return WORLD


def _sid():
    """This browser session's id. Locally the demo shares one store (it persists); hosted, every visitor gets their own."""
    return st.session_state.setdefault("sid", uuid.uuid4().hex[:12]) if PUBLIC else "shared"


@st.cache_resource(max_entries=8)
def _company(cid: str) -> CompanyData:
    return CompanyData(WORLD, cid, WORLD / "runtime" / "ui")


def company(cid: str) -> CompanyData:
    """The company's records are read once and shared; what the agent writes (drafts, holds) is per visitor when hosted."""
    base = _company(cid)
    if not PUBLIC:
        return base
    mine = st.session_state.setdefault("companies", {})
    if cid not in mine:
        from ..runtime.company import Runtime
        mine[cid] = copy.copy(base)
        mine[cid].runtime = Runtime(WORLD / "runtime" / "sessions" / _sid() / f"{cid}.sqlite")
    return mine[cid]


def _store_path():
    return WORLD / "learning" / ("demo.sqlite" if not PUBLIC else f"sessions/{_sid()}.sqlite")


def store() -> LessonStore:
    path = _store_path()
    if PUBLIC and not path.exists():            # a new visitor starts with the EXP-008 lessons, as in the video
        LessonStore(path)
        load_exp008_lessons()
    return LessonStore(path)


def load_exp008_lessons():
    """Copy the EXP-008 lesson store (mined by Muse, approved by the fixed review rule) into this demo store."""
    dst = _store_path()
    if EXP008:
        shutil.copy(EXP008[-1], dst)
        return True
    bundle = DEMO / "exp008_lessons.json"
    if not bundle.exists():
        return False
    _empty(dst)
    data = json.loads(bundle.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(dst)) as con, con:
        for table, rows in data.items():
            for r in rows:
                con.execute(f"insert into {table} ({','.join(r)}) values ({','.join('?' * len(r))})", list(r.values()))
    return True


def _empty(path):
    """Empty a lesson store in place (the running app may hold the file open, so it can't be deleted on Windows)."""
    LessonStore(path)                            # creates the schema if missing
    with closing(sqlite3.connect(path)) as con, con:
        for (t,) in con.execute("select name from sqlite_master where type = 'table'").fetchall():
            con.execute(f"delete from {t}")


def clear_lessons():
    p = _store_path()
    if p.exists():
        _empty(p)


@st.cache_resource
def harness_store() -> HarnessStore:
    """One harness for every client: how the agent works is shared; what it knows stays per company."""
    H = HarnessStore(ROOT / "data" / "harness" / "harness.sqlite")
    bundle = DEMO / "practice.json"
    if not H.practice() and bundle.exists():     # fresh checkout: show the saved EXP-010 practice results
        rows = json.loads(bundle.read_text(encoding="utf-8"))
        with sqlite3.connect(H.path) as con:
            for r in rows:
                con.execute(f"insert into practice ({','.join(r)}) values ({','.join('?' * len(r))})", list(r.values()))
    return H


def active_harness():
    return harness_store().active()["surfaces"]


def knowledge_for(cid):
    return store().active_for(cid, company(cid))


def recent_runs(limit=60):
    rows = []
    for p in _trace_files():
        rows += [json.loads(x) for x in reversed(p.read_text(encoding="utf-8").splitlines()) if x.strip()]
        if len(rows) >= limit:
            break
    return rows[:limit]


def broker(cid: str, use_lessons: bool, role="dispatcher", user="demo"):
    C = company(cid)
    knowledge, policies, advisories = store().active_for(cid, C) if use_lessons else ([], [], [])
    lessons = store().for_agent(cid, C) if use_lessons else []
    return Broker(C, Session(cid, role, user), policies, advisories, lessons, analysis=True), knowledge


_SPEND_LOCK = threading.Lock()


def _spend_file():
    return WORLD / "runtime" / f"live_calls_{date.today().isoformat()}.json"


def _calls_today():
    try:
        return json.loads(_spend_file().read_text(encoding="utf-8"))["calls"]
    except (OSError, ValueError, KeyError):
        return 0


def live_ready(model_key):
    """Why live mode is off, or None. Needs the model's key (a .env locally, or the host's secrets), this session's
    run budget and the app's daily budget."""
    try:
        muse.key_for(model_key)
    except muse.MissingKeyError:
        return f"Live mode is off here (no `{muse.KEYS[model_key]}` set). Use Replay."
    if st.session_state.get("live_runs", 0) >= LIVE_RUNS_PER_SESSION:
        return f"This session used its {LIVE_RUNS_PER_SESSION} live runs. Use Replay, or run it locally."
    if _calls_today() >= LIVE_CALLS_PER_DAY:
        return f"The demo's daily budget of {LIVE_CALLS_PER_DAY} live runs is used up. Use Replay, or run it locally."
    return None


def live_client(model_key):
    """The one way pages get a live Muse client: checks the key and both budgets, then counts the run.
    Returns (client, None), or (None, reason) to show instead."""
    with _SPEND_LOCK:
        blocked = live_ready(model_key)
        if blocked:
            return None, blocked
        st.session_state["live_runs"] = st.session_state.get("live_runs", 0) + 1
        f = _spend_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"calls": _calls_today() + 1}), encoding="utf-8")
    return muse.client(model_key), None


def run_live(cid, request, model_key, use_lessons, history=()):
    client, blocked = live_client(model_key)
    if blocked:
        raise muse.MissingKeyError(blocked)
    b, knowledge = broker(cid, use_lessons)
    turns = []
    for h in list(history)[-6:]:                 # the last few exchanges, so follow-ups make sense
        turns += [{"role": "user", "content": h["request"]}, {"role": "assistant", "content": h["run"]["reply"]}]
    r = graph.run(b, client, request, knowledge=knowledge, harness=active_harness(), history=turns, about=about(cid))
    trace.save(r, label=f"ui:{cid}:{'lessons' if use_lessons else 'cold'}")
    return r


def about(cid):
    """The saved business profile, as the agent reads it ("" until the owner saves one on the Business profile page)."""
    return profile.render(profile.latest(store(), cid))


def _trace_files():
    return sorted(trace.TRACE_DIR.glob("*.jsonl"), reverse=True) + ([DEMO / "replay_runs.jsonl"] if (DEMO / "replay_runs.jsonl").exists() else [])


def find_replay(cid, request, use_lessons):
    """The newest saved real run with the same company, request and knowledge setting (local traces, then the demo bundle)."""
    for p in _trace_files():
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            if r["company"] == cid and r["request"].strip() == request.strip() and bool(r.get("knowledge")) == use_lessons:
                return r
    return None


def replayable(cid, use_lessons):
    return [label for label, req in SUGGESTIONS.items() if find_replay(cid, req, use_lessons)]


def tool_steps(r):
    return [s for s in r["trace"] if s["type"] == "tool"]


def args_of(step):
    a = step["arguments"]
    return json.loads(a) if isinstance(a, str) else (a or {})


def summarize(step):
    """One readable line per tool result."""
    if not step["ok"]:
        return f"✗ {step['error']['code']}: {step['error']['message'][:120]}"
    res = step.get("result") or {}
    name = step["name"]
    if name == "find_site":
        m = res.get("matches", [])
        return ", ".join(f"{x['name']} ({x['town']})" for x in m[:3]) or "no match"
    if name == "list_open_orders":
        return f"{len(res.get('orders', []))} open orders"
    if name == "list_vehicles":
        return f"{len(res.get('vehicles', []))} vehicles"
    if name == "get_site_constraints":
        extra = ""
        if res.get("approved_policies"):
            extra = " · approved rule: " + "; ".join(p["rule"] for p in res["approved_policies"])
        if res.get("advisories"):
            extra += " · advice: " + "; ".join(a["text"] for a in res["advisories"])
        return f"site master: {res.get('recorded_in_site_master')}{extra}"
    if name == "create_dispatch_draft":
        return f"draft {res.get('draft_id')} · {res.get('vehicle_id')} · {res.get('load', {}).get('kg')} kg"
    if name == "check_vehicle_availability":
        return "free" if res.get("available") else f"not free ({res.get('status')}, held={res.get('held_by_draft')})"
    if name == "get_route_info":
        return f"{res.get('road_km_from_depot')} km · ~{res.get('drive_minutes')} min"
    return json.dumps(res, ensure_ascii=False, default=str)[:140]


def drafts(r):
    """Drafts created in a run, read from its trace (works for live runs and replays alike)."""
    out = []
    for s in tool_steps(r):
        if s["name"] == "create_dispatch_draft" and s["ok"]:
            out.append(s["result"])
        if s["name"] == "create_dispatch_drafts" and s["ok"]:
            out += [x for x in s["result"]["results"] if x["ok"]]
        if s["name"] == "cancel_dispatch_draft" and s["ok"]:
            out = [d for d in out if d["draft_id"] != (s.get("result") or {}).get("draft_id")]
    return out


def lessons_used(r):
    used = []
    text = r.get("reply", "")
    for k in r.get("knowledge", []):
        lid = k.rsplit("[", 1)[-1].rstrip("]").split()[-1] if "[" in k else ""
        if lid and lid in text:
            used.append(k)
    return used
