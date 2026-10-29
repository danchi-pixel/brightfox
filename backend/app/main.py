"""BrightFox API (FastAPI).

Runs on 127.0.0.1:7687 by default. The Vite frontend on :7686 proxies ``/api`` here, so the browser
only ever talks to one origin. In production one container serves the built web app and the API.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import Scope

from .auth import AuthMiddleware
from .config import APP_NAME, APP_VERSION, settings
from .content.checker import ContentError
from .content.registry import get_content
from .migrate import run_migrations
from .routers import auth as auth_router
from .routers import exams, family, learner, mocks, oral, studio, system, tutor, lab

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ucilnica")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_dirs()
    run_migrations()
    try:
        log.info("Content: %d topics", len(get_content().topics))
    except ContentError:
        log.exception("Topics could not be loaded; they are unavailable until the files are fixed")
    from sqlalchemy import func, select

    from .db import SessionLocal
    from .models import Family

    with SessionLocal() as db:
        if not db.scalar(select(func.count(Family.id))):
            log.warning("No family yet. Create one with: python -m app.manage create-family <slug> --name <name>")
    log.info("%s %s ready. Data folder: %s", APP_NAME, APP_VERSION, settings.data_dir)
    yield


app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION, lifespan=lifespan)

# Innermost first: sign-in check ...
app.add_middleware(AuthMiddleware)
# ... and reject requests whose Host header isn't expected (protects against DNS-rebinding attacks).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7686", "http://127.0.0.1:7686"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):  # pragma: no cover - defensive
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error."})


for r in (system.router, auth_router.router, family.router, studio.router, learner.router, tutor.router, exams.router,
          mocks.studio, mocks.learner, oral.router, lab.router):
    app.include_router(r)


# --------------------------------------------------------------------------- #
# Built web app (production: one container serves the UI and the API)
# --------------------------------------------------------------------------- #
class AssetFiles(StaticFiles):
    """Vite's hashed build assets never change, so they can be cached forever."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


if settings.static_dir and (settings.static_dir / "index.html").exists():
    _static = settings.static_dir
    if (_static / "assets").is_dir():
        app.mount("/assets", AssetFiles(directory=str(_static / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def web_app(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(404, "Not found")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static):
            return FileResponse(candidate)
        # Client-side routes (e.g. /l/3/learn/x) all load the app shell.
        return FileResponse(_static / "index.html", headers={"Cache-Control": "no-cache"})
