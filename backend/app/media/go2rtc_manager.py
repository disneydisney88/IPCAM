from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import yaml

from app.config import settings


def redact_uri(uri: str) -> str:
    parts = urlsplit(uri)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


class Go2RTCManager:
    def __init__(self) -> None:
        self.executable = settings.go2rtc_path
        self.config_path = settings.cache_dir / "go2rtc.yaml"
        self.process: subprocess.Popen[str] | None = None
        self.streams: dict[str, str] = {}
        self.monitor_task: asyncio.Task | None = None
        self.monitor_stop = asyncio.Event()
        self.consecutive_failures = 0
        self.restarts = 0
        self.last_health: dict[str, object] = {"available": self.available, "running": False, "message": "NOT CHECKED"}

    @property
    def available(self) -> bool:
        return self.executable.exists()

    async def health(self) -> dict[str, object]:
        if not self.available:
            return {"available": False, "running": False, "message": "STREAM GATEWAY NOT AVAILABLE"}
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{settings.go2rtc_api}/api")
            return {"available": True, "running": response.status_code < 500, "message": "READY"}
        except httpx.TimeoutException:
            return {"available": True, "running": False, "state": "timeout", "message": "STREAM GATEWAY TIMEOUT"}
        except httpx.HTTPError:
            return {"available": True, "running": False, "state": "offline", "message": "STREAM GATEWAY OFFLINE"}

    async def ensure_healthy(self) -> dict[str, object]:
        health = await self.health()
        if health["available"] and not health["running"]:
            restarted = self.reload()
            if restarted:
                await __import__("asyncio").sleep(0.25)
                health = await self.health()
            health["recovery_attempted"] = restarted
        return health

    async def monitor_once(self) -> dict[str, object]:
        health = await self.health()
        self.last_health = health
        if health["available"] and not health["running"]:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 2 and self.reload():
                self.restarts += 1
                health = {**health, "recovery_attempted": True, "restart_count": self.restarts}
        else:
            self.consecutive_failures = 0
        self.last_health = health
        return health

    def start_monitor(self) -> None:
        if not self.monitor_task or self.monitor_task.done():
            self.monitor_stop = asyncio.Event()
            self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitor(self) -> None:
        self.monitor_stop.set()
        if self.monitor_task:
            self.monitor_task.cancel()
            try: await self.monitor_task
            except asyncio.CancelledError: pass
            self.monitor_task = None

    async def _monitor_loop(self) -> None:
        while True:
            await self.monitor_once()
            try: await asyncio.wait_for(self.monitor_stop.wait(), timeout=min(60, 5 * 2 ** min(self.consecutive_failures, 3)))
            except asyncio.TimeoutError: continue
            return

    @staticmethod
    def classify_stream_error(message: str) -> str:
        value = message.lower()
        if any(item in value for item in ("401", "403", "unauthorized", "authentication")): return "authentication_failed"
        if "timeout" in value or "timed out" in value: return "timeout"
        return "stream_unavailable"

    def _write_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"api": {"listen": "127.0.0.1:1984"}, "webrtc": {"listen": "127.0.0.1:8555"}, "streams": self.streams}
        self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def start(self) -> bool:
        if not self.available:
            return False
        self._write_config()
        self.process = subprocess.Popen(
            [str(self.executable), "-config", str(self.config_path)],
            cwd=str(settings.cache_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), text=True,
        )
        return True

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None

    def register_stream(self, camera_id: int, uri: str, kind: str = "sub") -> str:
        name = f"camera_{camera_id}_{kind}"
        self.streams[name] = uri
        self._write_config()
        return name

    def player_url(self, stream_name: str) -> str:
        return f"{settings.go2rtc_api}/stream.html?src={stream_name}&mode=webrtc"

    def reload(self) -> bool:
        if not self.available:
            return False
        if self.process and self.process.poll() is None:
            self.stop()
        return self.start()

    def remove_stream(self, camera_id: int, kind: str = "sub") -> None:
        self.streams.pop(f"camera_{camera_id}_{kind}", None)
        self._write_config()


manager = Go2RTCManager()
