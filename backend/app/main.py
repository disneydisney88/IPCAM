from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.database.core import init_db
from app.services.admin_auth import admin_auth
from app.services.scheduler import scheduler
from app.media.go2rtc_manager import manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler.start()
    manager.start_monitor()
    yield
    await manager.stop_monitor()
    await scheduler.stop()


app = FastAPI(title="IPCAM Scanner API", version="0.5.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard lock: every /api call needs a short-lived admin unlock token.
# Exempt: health, admin setup/unlock themselves, SSE scan events (EventSource
# cannot send headers) and snapshot JPEGs (<img> tags cannot send headers).
_LOCK_EXEMPT_PREFIXES = ("/api/health", "/api/admin/status", "/api/admin/setup", "/api/admin/unlock")
_LOCK_EXEMPT_PATHS = re.compile(r"^/api/scans/\d+/events$|^/api/cameras/\d+/snapshot\.jpg$")


@app.middleware("http")
async def dashboard_lock_middleware(request: Request, call_next):
    path = request.url.path
    if (os.environ.get("IPCAM_DASHBOARD_LOCK", "1") != "0" and path.startswith("/api/")
            and not path.startswith(_LOCK_EXEMPT_PREFIXES) and not _LOCK_EXEMPT_PATHS.match(path)):
        if not admin_auth.configured():
            return JSONResponse({"detail": "Admin password setup required"}, status_code=428,
                                headers={"X-Dashboard-Lock": "setup"})
        try:
            admin_auth.require(request.headers.get("X-Admin-Unlock"))
        except ValueError as exc:
            status = 429 if "locked" in str(exc) else 401
            return JSONResponse({"detail": str(exc)}, status_code=status,
                                headers={"X-Dashboard-Lock": "locked"})
    return await call_next(request)


app.include_router(router)

frontend_dist = __import__("pathlib").Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="dashboard")
else:
    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "IPCAM Scanner API", "docs": "/docs", "setup": "Build frontend first"}
