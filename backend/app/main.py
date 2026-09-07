from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.database.core import init_db
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


app = FastAPI(title="IPCAM Scanner API", version="0.3.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

frontend_dist = __import__("pathlib").Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="dashboard")
else:
    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "IPCAM Scanner API", "docs": "/docs", "setup": "Build frontend first"}
