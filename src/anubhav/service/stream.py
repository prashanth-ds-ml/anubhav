"""Live requests for a streaming client: the run happens in a worker thread and writes each event to the store as it
happens; a reader (the SSE endpoint) follows the store by seq, so it can drop and reconnect without losing anything.
A replay streams a saved run's events the same way."""

import threading
import time
import uuid

from .. import events, trace
from . import checkpoints, runs

_LOCK = threading.Lock()
_LIVE = {}          # run_id -> {"sid", "status": running | done | error, "stop", "error"}
MAX_TRACKED = 500   # finished runs are forgotten oldest first; their events stay in the store


def store():
    return events.EventStore(trace.TRACE_DIR / "events.sqlite")


def _track(run_id, **info):
    with _LOCK:
        _LIVE.setdefault(run_id, {}).update(info)
        while len(_LIVE) > MAX_TRACKED:
            old = next((k for k, v in _LIVE.items() if v.get("status") != "running"), None)
            if old is None:
                break
            del _LIVE[old]


def status(run_id):
    with _LOCK:
        return dict(_LIVE.get(run_id) or {})


def start(ws, client, cid, request, use_lessons, history=(), team=False, harness=None, resume=None):
    """Start one live request; returns its run_id at once. The caller has passed the spend guard."""
    run_id = uuid.uuid4().hex[:10]
    st = store()
    em = events.Emitter(run_id, sink=lambda e: st.save([e]))
    _track(run_id, sid=ws.sid, status="running", stop=None)

    def work():
        try:
            r = runs.run_with(ws, client, cid, request, use_lessons, history, team, harness, hooks=em, run_id=run_id, resume=resume)
            _track(run_id, status="done", stop=r["stop"])
        except Exception as e:      # the reader must always get an end; keys never appear in these messages
            if resume:
                checkpoints.reopen(resume["run_id"])
            _track(run_id, status="error", stop="error", error=type(e).__name__)
    threading.Thread(target=work, daemon=True, name=f"run-{run_id}").start()
    return run_id


def follow(run_id, after=-1, poll_s=0.1, timeout_s=300, heartbeat_s=None):
    """Yield a live run's events after `after` as they appear, ending when the run has ended and all were read.
    With heartbeat_s, yields None when nothing happened for that long (a long model call), so proxies keep the line open."""
    st = store()
    deadline = time.monotonic() + timeout_s
    quiet = time.monotonic()
    while True:
        ended = status(run_id).get("status") != "running"     # read before the events, so none are missed
        for e in st.load(run_id, after):
            after, quiet = e["seq"], time.monotonic()
            yield e
        if ended or time.monotonic() > deadline:
            return
        if heartbeat_s and time.monotonic() - quiet > heartbeat_s:
            quiet = time.monotonic()
            yield None
        time.sleep(poll_s)


def replay_events(run, after=-1):
    """A saved run's events after `after` (the demo bundle's runs have none stored: built on the fly)."""
    return [e for e in events.from_run(run) if e["seq"] > after]


def ended_stop(run_id):
    return status(run_id).get("stop")


__all__ = ["start", "follow", "status", "replay_events", "ended_stop", "store", "runs"]
