from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.database.core import session_scope
from app.models import ExternalTarget, SchedulerRun, Setting
from app.scanners.external import scan_external_target
from app.services.audit import record_audit


DEFAULT_CONFIG: dict[str, Any] = {"enabled": False, "interval_minutes": 60, "scan_mode": "quick", "target_timeout_seconds": 15, "last_run": None}


class ExternalScanScheduler:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.running = False
        self.stopping = False
        self.cancel_requested = False
        self.active_scan_task: asyncio.Task | None = None
        self.shutdown_requested = False
        self.active_targets: set[str] = set()

    def claim_target(self, target_key: str) -> bool:
        if target_key in self.active_targets: return False
        self.active_targets.add(target_key)
        return True

    def release_target(self, target_key: str) -> None:
        self.active_targets.discard(target_key)

    def config(self) -> dict[str, Any]:
        with session_scope() as db:
            setting = db.get(Setting, "external_scan_scheduler")
            return {**DEFAULT_CONFIG, **(setting.value if setting else {})}

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        config = {**self.config(), **values}
        with session_scope() as db:
            setting = db.get(Setting, "external_scan_scheduler")
            if setting:
                setting.value = config
            else:
                db.add(Setting(key="external_scan_scheduler", value=config))
            record_audit(db, "scheduler.updated", details={key: config[key] for key in ("enabled", "interval_minutes", "scan_mode", "target_timeout_seconds")})
        self.wake()
        return self.status()

    def status(self) -> dict[str, Any]:
        config = self.config()
        next_run = None
        if config["enabled"] and config.get("last_run"):
            last = datetime.fromisoformat(config["last_run"])
            next_run = (last + timedelta(minutes=config["interval_minutes"])).isoformat()
        state = "stopping" if self.stopping else "running" if self.running else "stopped"
        return {**config, "running": self.running, "state": state, "next_run": next_run}

    def start(self) -> None:
        if not self.task or self.task.done():
            self.stop_event = asyncio.Event()
            self.shutdown_requested = False
            self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.shutdown_requested = True
        await self.cancel_run()
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    def wake(self) -> None:
        self.stop_event.set()

    async def cancel_run(self) -> dict[str, Any]:
        if not self.running:
            return self.status()
        self.stopping = True
        self.cancel_requested = True
        if self.active_scan_task and not self.active_scan_task.done():
            self.active_scan_task.cancel()
        with session_scope() as db:
            record_audit(db, "scheduler.stop_requested", details={})
        return self.status()

    async def run_once(self, respect_enabled: bool = False) -> dict[str, int]:
        if self.running:
            return {"scanned": 0, "failed": 0, "cancelled": 0}
        self.running = True
        self.stopping = False
        self.cancel_requested = False
        scanned = failed = cancelled = 0
        try:
            config = self.config()
            with session_scope() as db:
                targets = list(db.scalars(select(ExternalTarget).where(ExternalTarget.enabled.is_(True))).all())
                target_data = [(item.id, item.name, item.host, item.port_overrides) for item in targets]
                history = SchedulerRun(targets_count=len(target_data), status="queued")
                db.add(history)
                db.flush()
                run_id = history.id
                history.status = "running"
            for target_id, name, host, ports in target_data:
                if self.cancel_requested or (respect_enabled and not self.config()["enabled"]):
                    cancelled += 1
                    break
                target_value = f"{host}:{ports}" if ports else host
                target_key = str(target_id)
                if not self.claim_target(target_key):
                    failed += 1
                    with session_scope() as db:
                        record_audit(db, "external_scan.scheduled", "failed", target_id=target_id,
                                     target_name=name, details={"error": "target already has an active scan"})
                    continue
                try:
                    self.active_scan_task = asyncio.create_task(scan_external_target(target_value, mode=config["scan_mode"]))
                    await asyncio.wait_for(self.active_scan_task, timeout=config["target_timeout_seconds"])
                    scanned += 1
                    with session_scope() as db:
                        target = db.get(ExternalTarget, target_id)
                        if target:
                            target.last_scan = datetime.now(timezone.utc)
                        record_audit(db, "external_scan.scheduled", target_id=target_id, target_name=name,
                                     details={"mode": config["scan_mode"]})
                except asyncio.CancelledError:
                    cancelled += 1
                    with session_scope() as db:
                        record_audit(db, "external_scan.scheduled", "cancelled", target_id=target_id,
                                     target_name=name, details={"mode": config["scan_mode"]})
                    break
                except asyncio.TimeoutError:
                    failed += 1
                    with session_scope() as db:
                        record_audit(db, "external_scan.scheduled", "failed", target_id=target_id,
                                     target_name=name, details={"error": "target timeout", "timeout_seconds": config["target_timeout_seconds"]})
                except Exception as exc:
                    failed += 1
                    with session_scope() as db:
                        record_audit(db, "external_scan.scheduled", "failed", target_id=target_id,
                                     target_name=name, details={"error": str(exc)})
                finally:
                    self.release_target(target_key)
            with session_scope() as db:
                setting = db.get(Setting, "external_scan_scheduler")
                values = {**DEFAULT_CONFIG, **(setting.value if setting else {})}
                values["last_run"] = datetime.now(timezone.utc).isoformat()
                if setting:
                    setting.value = values
                else:
                    db.add(Setting(key="external_scan_scheduler", value=values))
                history = db.get(SchedulerRun, run_id)
                if history:
                    completed = datetime.now(timezone.utc)
                    history.completed_at = completed
                    history.succeeded = scanned
                    history.failed = failed
                    history.cancelled = cancelled
                    history.status = "cancelled" if cancelled else "failed" if failed and not scanned else "completed"
                    started = history.started_at.replace(tzinfo=timezone.utc) if history.started_at.tzinfo is None else history.started_at
                    history.duration_seconds = max(0, (completed - started).total_seconds())
            return {"scanned": scanned, "failed": failed, "cancelled": cancelled}
        finally:
            self.active_scan_task = None
            self.running = False
            self.stopping = False
            self.cancel_requested = False

    async def _loop(self) -> None:
        while True:
            config = self.config()
            delay = 30.0
            if config["enabled"]:
                if not config.get("last_run"):
                    delay = 0
                else:
                    due = datetime.fromisoformat(config["last_run"]) + timedelta(minutes=config["interval_minutes"])
                    delay = max(0, (due - datetime.now(timezone.utc)).total_seconds())
            self.stop_event.clear()
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=max(delay, 0.1))
                continue
            except asyncio.TimeoutError:
                if config["enabled"]:
                    await self.run_once(respect_enabled=True)
                    if self.shutdown_requested:
                        return


scheduler = ExternalScanScheduler()
