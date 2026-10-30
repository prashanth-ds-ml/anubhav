"""The demo app as a judge sees it when hosted: no keys, ANUBHAV_PUBLIC. Every page opens, live buttons are off instead
of crashing, Replay offers only saved runs, and one visitor's actions never change another visitor's state.
Runs the real app in-process (Streamlit AppTest) on the demo world; no model calls."""

import gc
import re
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from anubhav import muse
from anubhav.ui import core

PAGES = ["app_pages/workbench.py", "app_pages/profile.py", "app_pages/new_tools.py", "app_pages/learned.py", "app_pages/share.py", "app_pages/proof.py", "app_pages/logs.py",
         "app_pages/report.py", "app_pages/learning_lab.py", "app_pages/skills.py", "app_pages/tuning.py"]
LIVE_BUTTONS = {"app_pages/learned.py": "Learn from my records", "app_pages/learning_lab.py": "Mine my records now",
                "app_pages/skills.py": "Practice now (active version)", "app_pages/tuning.py": "Ask Muse for a patch"}


@pytest.fixture
def visitor(monkeypatch):
    for k in muse.KEYS.values():            # muse is imported (and .env read) above, so the keys stay off
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(core, "PUBLIC", True)
    apps = []

    def new():
        at = AppTest.from_file(str(core.ROOT / "streamlit_app.py"), default_timeout=300)
        at.run()
        apps.append(at)
        return at
    yield new
    gc.collect()                            # Windows can't delete a database file while a closed-over handle lingers
    for at in apps:
        sid = at.session_state["sid"] if "sid" in at.session_state else None
        if sid:
            shutil.rmtree(core.WORLD / "runtime" / "sessions" / sid, ignore_errors=True)
            (core.WORLD / "learning" / "sessions" / f"{sid}.sqlite").unlink(missing_ok=True)


def test_every_page_opens_without_keys(visitor):
    at = visitor()
    for page in PAGES:
        at.switch_page(page)
        at.run()
        assert not at.exception, (page, [e.value for e in at.exception])


def test_live_buttons_are_off_without_keys_and_say_why(visitor):
    at = visitor()
    for page, label in LIVE_BUTTONS.items():
        at.switch_page(page)
        at.run()
        (b,) = [x for x in at.button if x.label == label]
        assert b.disabled and "Use Replay" in (b.help or ""), page


def test_a_new_visitor_starts_with_the_exp008_lessons(visitor):
    at = visitor()
    assert any("approved lessons for T01" in c.value and not c.value.startswith("0 ") for c in at.sidebar.caption)


def test_replay_offers_only_requests_with_a_saved_run(visitor):
    at = visitor()
    offered = at.pills[0].options if at.pills else []
    assert offered and set(offered) == set(core.replayable("T01", False))


def test_one_visitor_clearing_lessons_does_not_touch_another(visitor):
    a, b = visitor(), visitor()
    (clear,) = [x for x in a.sidebar.button if x.label == "Clear all lessons"]
    clear.click()
    a.run()
    assert any(c.value.startswith("0 approved") for c in a.sidebar.caption)
    b.run()
    assert not any(c.value.startswith("0 approved") for c in b.sidebar.caption)


def test_logs_page_shows_a_run_as_plan_act_observe(visitor):
    at = visitor()
    at.switch_page("app_pages/logs.py")
    at.run()
    assert not at.exception
    assert any("Agent runs" in m.label for m in at.metric)
    assert any(m.value.startswith("**Request:**") for m in at.markdown)      # the newest saved run is opened
    assert any(re.match(r"[a-z_]+\(", e.label) for e in at.expander)        # at least one "tool(args)" act row


def test_a_visitor_saves_a_business_profile_and_only_they_see_it(visitor):
    a, b = visitor(), visitor()
    a.switch_page("app_pages/profile.py"); a.run()
    a.text_input[0].input("3PL for FMCG brands")
    a.button[0].click(); a.run()
    assert not a.exception and any("3PL for FMCG brands" in c.value for c in a.code)
    b.switch_page("app_pages/profile.py"); b.run()
    assert not b.code and any("Nothing yet" in i.value for i in b.info)


def test_a_reused_query_is_checked_approved_and_offered_to_the_agent(visitor, monkeypatch):
    import json
    C = core._company("T01")
    towns = sorted({s["town"] for s in C.sites.values()})
    q = ("SELECT COUNT(*) FROM trip_outcomes t JOIN sites s ON s.site_id = t.site_id WHERE s.town = '{}' "
         "AND t.status = 'returned' AND t.arrived_at BETWEEN '{}' AND '{}'")
    runs = [{"run_id": f"r{i}", "company": "T01", "request": req, "trace": [{"type": "tool", "name": "run_query", "ok": True,
             "arguments": json.dumps({"sql": q.format(town, a, b), "purpose": "returned stops in a town"}), "result": {"row_count": 1}}]}
            for i, (req, town, a, b) in enumerate([("returns in town A?", towns[0], "2026-09-01", "2026-09-30"),
                                                   ("returns in town B?", towns[1], "2026-08-01", "2026-08-31")])]
    monkeypatch.setattr(core, "recent_runs", lambda limit=60: runs)
    at = visitor()
    at.switch_page("app_pages/new_tools.py"); at.run()
    assert next(m for m in at.metric if m.label == "Reused queries").value == "1"
    next(b for b in at.button if b.label == "Check it as a tool").click(); at.run()
    assert not at.exception and next(m for m in at.metric if m.label == "Waiting for approval").value == "1"
    next(b for b in at.button if b.label == "Approve as a tool").click(); at.run()
    assert next(m for m in at.metric if m.label == "Tools in use").value == "1"
    from anubhav.learning import newtools
    from anubhav.learning.store import LessonStore
    from anubhav.runtime.broker import Broker, Session
    mine = newtools.tools(LessonStore(core.WORLD / "learning" / "sessions" / f"{at.session_state['sid']}.sqlite"), "T01", "active")
    b = Broker(C, Session("T01"), learned_tools=mine)
    assert [t.name for t in b.list_tools() if t.category == "learned_tools"] == [mine[0]["name"]]
