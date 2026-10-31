"""The FastAPI app: one error shape, per-visitor state, routes under /api. The built web app will be served from / here."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from ..data.config import ROOT
from ..harness.store import PatchError
from ..learning.store import ReviewError
from ..service import session
from .deps import ApiError, Visitors
from .routes import api

log = logging.getLogger("anubhav.api")


def _error(status, code, message, **extra):
    return JSONResponse({"error": {"code": code, "message": message, **extra}}, status_code=status)


def create_app(public=None, world=None, replay_pace=0.05) -> FastAPI:
    app = FastAPI(title="Anubhav API", version="1.0.0", description="See contracts/api.md. Drafts only; nothing is dispatched.")
    app.state.public = session.PUBLIC if public is None else public
    app.state.world = session.ensure_world(world or session.WORLD)
    app.state.visitors = Visitors()
    app.state.replay_pace = replay_pace

    @app.exception_handler(ApiError)
    def api_error(_: Request, e: ApiError):
        return _error(e.status, e.code, e.message, **e.extra)

    @app.exception_handler(RequestValidationError)
    def bad_request(_: Request, e: RequestValidationError):
        first = e.errors()[0]
        return _error(422, "BAD_ARGS", f"{'.'.join(map(str, first['loc']))}: {first['msg']}")

    @app.exception_handler(HTTPException)
    def http_error(_: Request, e: HTTPException):
        return _error(e.status_code, "NOT_FOUND" if e.status_code == 404 else "HTTP_ERROR", str(e.detail))

    @app.exception_handler(ReviewError)
    def review_error(_: Request, e: ReviewError):
        return _error(409, "CONFLICT", str(e))

    @app.exception_handler(PatchError)
    def patch_error(_: Request, e: PatchError):
        return _error(409, "CONFLICT", str(e))

    @app.exception_handler(PermissionError)
    def forbidden(_: Request, e: PermissionError):
        return _error(403, "PERMISSION_DENIED", str(e))

    @app.exception_handler(ValueError)
    def conflict(_: Request, e: ValueError):
        return _error(409, "CONFLICT", str(e))

    @app.exception_handler(Exception)
    def internal(_: Request, e: Exception):      # the detail stays in the server log, never in a response
        log.exception("unhandled")
        return _error(500, "INTERNAL", "something went wrong on the server")

    app.include_router(api)
    dist = ROOT / "web" / "dist"
    if dist.exists():           # the built web app, once there is one; /api and /docs stay as they are
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
