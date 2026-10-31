"""One visitor's workspace: their view of the company data, lesson store and live-run budget. `state` is any dict-like
the front end keeps per visitor (Streamlit's session_state, or a plain dict in the API). Locally everyone shares one
store (it persists); hosted, every visitor gets their own drafts and lessons."""

import copy
import functools
import json
import os
import shutil
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .. import muse
from ..data.config import ROOT
from ..harness.store import HarnessStore
from ..learning import newtools, profile
from ..learning.store import LessonStore
from ..runtime.broker import Broker, Session
from ..runtime.company import CompanyData, Runtime

WORLD = ROOT / "data" / "worlds" / "full_seed20261104"
EXP008 = sorted((ROOT / "artifacts" / "learning").glob("exp008_*_rep0.sqlite"))
DEMO = ROOT / "demo"            # git-tracked bundle for a fresh (hosted) checkout: saved real runs, EXP-008 lessons, practice
LIVE_RUNS_PER_SESSION = 8       # spend cap for live model calls on a public deployment
LIVE_CALLS_PER_DAY = 60         # and for the whole app, across every visitor and page (reloading doesn't reset it)
LIVE_CALLS_PER_DAY_BY_MODEL = {"open": 30}    # Baseten has the smaller credit, kept for judges (D-048): at most $12 a day
PUBLIC = os.environ.get("ANUBHAV_PUBLIC") == "1"   # hosted for judges: each visitor gets their own drafts and lessons
COMPANIES = {"T01": "Sri Kakatiya Logistics", "T02": "Ramappa Carriers", "T03": "Deccan Freight Services",
             "TNEW": "Bhadrakali Transport Co (new)"}
AGENT_MODEL = "spark"           # the default for live runs (owner, D-046); people can switch to Muse Spark Open. Every measured result is on Open
MODELS = {"Replay (free)": None, "Muse Spark 1.3": "spark", "Muse Spark Open": "open"}
SUGGESTIONS = {
    "Roman Telugu": "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku.",
    "Telugu": "రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు.",
    "English": "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.",
    "Mixed": "Jangaon Lakshmi order ki suitable vehicle choose chesi draft create cheyyi, confirm cheyyaku.",
    "Nickname": "Pedda godown load ki bandi pettu.",
    "Ambiguous": "Warangal load ki bandi pettu.",
    "New tool": "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?",
}

_WORLD_LOCK = threading.Lock()
_SPEND_LOCK = threading.Lock()


def ensure_world(world=WORLD):
    """A fresh checkout has no data/ (git-ignored): generate the demo world from its seed. Deterministic, ~1 minute."""
    with _WORLD_LOCK:
        if not (Path(world) / "manifest.json").exists():
            from ..data import generate
            generate.main(["--full"])
    return world


@functools.lru_cache(maxsize=8)
def shared_company(cid: str, world=WORLD) -> CompanyData:
    return CompanyData(world, cid, Path(world) / "runtime" / "ui")


@functools.lru_cache(maxsize=4)
def _harness(path):
    H = HarnessStore(path)
    bundle = DEMO / "practice.json"
    if not H.practice() and bundle.exists():     # fresh checkout: show the saved EXP-010 practice results
        rows = json.loads(bundle.read_text(encoding="utf-8"))
        with closing(sqlite3.connect(H.path)) as con, con:
            for r in rows:
                con.execute(f"insert into practice ({','.join(r)}) values ({','.join('?' * len(r))})", list(r.values()))
    return H


def harness_store(path=ROOT / "data" / "harness" / "harness.sqlite") -> HarnessStore:
    """One harness for every client: how the agent works is shared; what it knows stays per company."""
    return _harness(path)


def _empty(path):
    """Empty a lesson store in place (the running app may hold the file open, so it can't be deleted on Windows)."""
    LessonStore(path)                            # creates the schema if missing
    with closing(sqlite3.connect(path)) as con, con:
        for (t,) in con.execute("select name from sqlite_master where type = 'table'").fetchall():
            con.execute(f"delete from {t}")


@dataclass
class Workspace:
    sid: str = "shared"
    public: bool = False
    state: object = field(default_factory=dict)     # per-visitor mapping: "companies", "live_runs"
    world: Path = WORLD

    # ---------- data
    def company(self, cid: str) -> CompanyData:
        """The company's records are read once and shared; what the agent writes (drafts, holds) is per visitor when hosted."""
        base = shared_company(cid, self.world)
        if not self.public:
            return base
        mine = self.state.setdefault("companies", {})
        if cid not in mine:
            mine[cid] = copy.copy(base)
            mine[cid].runtime = Runtime(Path(self.world) / "runtime" / "sessions" / self.sid / f"{cid}.sqlite")
        return mine[cid]

    def store_path(self) -> Path:
        return Path(self.world) / "learning" / ("demo.sqlite" if not self.public else f"sessions/{self.sid}.sqlite")

    def store(self) -> LessonStore:
        path = self.store_path()
        if self.public and not path.exists():    # a new visitor starts with the EXP-008 lessons, as in the video
            LessonStore(path)
            self.load_exp008_lessons()
        return LessonStore(path)

    def load_exp008_lessons(self):
        """Copy the EXP-008 lesson store (mined by Muse, approved by the fixed review rule) into this demo store."""
        dst = self.store_path()
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

    def clear_lessons(self):
        p = self.store_path()
        if p.exists():
            _empty(p)

    def knowledge_for(self, cid):
        return self.store().active_for(cid, self.company(cid))

    def about(self, cid):
        """The saved business profile, as the agent reads it ("" until the owner saves one)."""
        return profile.render(profile.latest(self.store(), cid))

    def has_learned_tools(self, cid):
        return bool(newtools.tools(self.store(), cid, "active"))

    def broker_args(self, cid, use_lessons):
        """What a broker for this visitor is made from: (knowledge, policies, advisories, lessons, learned tools)."""
        C = self.company(cid)
        knowledge, policies, advisories = self.store().active_for(cid, C) if use_lessons else ([], [], [])
        lessons = self.store().for_agent(cid, C) if use_lessons else []
        return knowledge, policies, advisories, lessons, newtools.tools(self.store(), cid, "active")

    def broker(self, cid: str, use_lessons: bool, role="dispatcher", user="demo"):
        knowledge, policies, advisories, lessons, learned = self.broker_args(cid, use_lessons)
        return Broker(self.company(cid), Session(cid, role, user), policies, advisories, lessons, analysis=True,
                      learned_tools=learned), knowledge

    # ---------- the spend guard: every live model call in the app comes through here
    def _spend_file(self):
        return Path(self.world) / "runtime" / f"live_calls_{date.today().isoformat()}.json"

    def calls_today(self, model_key=None):
        try:
            data = json.loads(self._spend_file().read_text(encoding="utf-8"))
            return data.get("by_model", {}).get(model_key, 0) if model_key else data["calls"]
        except (OSError, ValueError, KeyError):
            return 0

    def live_runs_left(self):
        return max(0, min(LIVE_RUNS_PER_SESSION - self.state.get("live_runs", 0), LIVE_CALLS_PER_DAY - self.calls_today()))

    def live_ready(self, model_key):
        """Why live mode is off, or None. Needs the model's key (a .env locally, or the host's secrets), this session's
        run budget and the app's daily budget."""
        try:
            muse.key_for(model_key)
        except muse.MissingKeyError:
            return f"Live mode is off here (no `{muse.KEYS[model_key]}` set). Use Replay."
        if self.state.get("live_runs", 0) >= LIVE_RUNS_PER_SESSION:
            return f"This session used its {LIVE_RUNS_PER_SESSION} live runs. Use Replay, or run it locally."
        if self.calls_today() >= LIVE_CALLS_PER_DAY:
            return f"The demo's daily budget of {LIVE_CALLS_PER_DAY} live runs is used up. Use Replay, or run it locally."
        cap = LIVE_CALLS_PER_DAY_BY_MODEL.get(model_key)
        if cap is not None and self.calls_today(model_key) >= cap:
            return f"This model's daily budget of {cap} live runs is used up. Pick another model, or use Replay."
        return None

    def live_client(self, model_key):
        """The one way to get a live Muse client: checks the key and both budgets, then counts the run.
        Returns (client, None), or (None, reason) to show instead."""
        with _SPEND_LOCK:
            blocked = self.live_ready(model_key)
            if blocked:
                return None, blocked
            self.state["live_runs"] = self.state.get("live_runs", 0) + 1
            f = self._spend_file()
            f.parent.mkdir(parents=True, exist_ok=True)
            by_model = {k: self.calls_today(k) for k in muse.KEYS}
            by_model[model_key] += 1
            f.write_text(json.dumps({"calls": self.calls_today() + 1, "by_model": by_model}), encoding="utf-8")
        return muse.client(model_key), None
