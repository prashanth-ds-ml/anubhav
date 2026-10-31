"""What every route needs: this visitor's workspace, a valid company, the public-host guard, and one error shape."""

import re
import threading
import uuid
from collections import OrderedDict

from fastapi import Depends, Request, Response

from ..service.session import COMPANIES, Workspace

COOKIE = "anubhav_sid"
SID = re.compile(r"[0-9a-f]{12}")       # a sid names files on disk: only this exact shape is ever accepted
MAX_VISITORS = 2000


class ApiError(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


class Visitors:
    """Per-visitor state, kept in memory (their drafts and lessons are on disk and survive a restart)."""

    def __init__(self):
        self.lock, self.states = threading.Lock(), OrderedDict()

    def state(self, sid):
        with self.lock:
            s = self.states.setdefault(sid, {})
            self.states.move_to_end(sid)
            while len(self.states) > MAX_VISITORS:
                self.states.popitem(last=False)
            return s


def workspace(request: Request, response: Response) -> Workspace:
    cfg = request.app.state
    if not cfg.public:          # locally the demo is one shared workspace
        return Workspace("shared", False, cfg.visitors.state("shared"), cfg.world)
    sid = request.cookies.get(COOKIE) or ""
    if not SID.fullmatch(sid):
        sid = uuid.uuid4().hex[:12]
        response.set_cookie(COOKIE, sid, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return Workspace(sid, True, cfg.visitors.state(sid), cfg.world)


Ws = Depends(workspace)


def company_id(company: str = "T01") -> str:
    if company not in COMPANIES:
        raise ApiError(404, "NOT_FOUND", f"unknown company {company}; companies: {', '.join(COMPANIES)}")
    return company


Cid = Depends(company_id)


def local_only(ws: Workspace = Ws):
    """Shared or paid actions aren't open to visitors on the public host (decided Oct 31: as the Streamlit buttons)."""
    if ws.public:
        raise ApiError(403, "READ_ONLY_PUBLIC", "this action is available when you run it locally")


LocalOnly = Depends(local_only)


def live(ws: Workspace, model_key: str):
    """A live client through the spend guard, or an error that says why not."""
    client, blocked = ws.live_client(model_key)
    if blocked:
        raise ApiError(409, "CAP_REACHED" if "used" in blocked else "NO_KEY", blocked)
    return client
