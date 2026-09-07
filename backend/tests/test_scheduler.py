import asyncio

from sqlalchemy import select

from app.database.core import session_scope
from app.models import AuditLog, ExternalTarget, SchedulerRun
from app.services.scheduler import ExternalScanScheduler


def test_scheduler_cancels_active_target_without_marking_success(monkeypatch):
    started = asyncio.Event()

    async def slow_scan(_target, mode="quick"):
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr("app.services.scheduler.scan_external_target", slow_scan)
    with session_scope() as db:
        for existing in db.scalars(select(ExternalTarget)).all():
            existing.enabled = False
        target = ExternalTarget(name="Cancellation target", host="203.0.113.77", enabled=True)
        db.add(target)
        db.flush()
        target_id = target.id

    async def scenario():
        instance = ExternalScanScheduler()
        instance.update({"enabled": True, "interval_minutes": 60, "scan_mode": "quick"})
        run_task = asyncio.create_task(instance.run_once())
        await asyncio.wait_for(started.wait(), timeout=2)
        assert instance.status()["state"] == "running"
        stopping = await instance.cancel_run()
        assert stopping["state"] == "stopping"
        result = await asyncio.wait_for(run_task, timeout=2)
        assert result["cancelled"] == 1
        assert instance.status()["state"] == "stopped"
        instance.update({"enabled": False})

    asyncio.run(scenario())
    with session_scope() as db:
        target = db.get(ExternalTarget, target_id)
        assert target.last_scan is None
        event = db.scalar(select(AuditLog).where(
            AuditLog.action == "external_scan.scheduled", AuditLog.target_id == target_id,
            AuditLog.status == "cancelled",
        ))
        assert event is not None
        history = db.scalar(select(SchedulerRun).order_by(SchedulerRun.id.desc()))
        assert history.status == "cancelled"
        assert history.cancelled == 1
        assert history.completed_at is not None
        assert history.duration_seconds is not None


def test_disabled_scheduler_does_not_start_scheduled_run(monkeypatch):
    calls = 0

    async def counted_scan(_target, mode="quick"):
        nonlocal calls
        calls += 1

    monkeypatch.setattr("app.services.scheduler.scan_external_target", counted_scan)

    async def scenario():
        instance = ExternalScanScheduler()
        instance.update({"enabled": False, "interval_minutes": 60, "scan_mode": "quick"})
        result = await instance.run_once(respect_enabled=True)
        assert result["scanned"] == 0

    asyncio.run(scenario())
    assert calls == 0


def test_target_timeout_records_failure_and_history(monkeypatch):
    async def timed_out_scan(_target, mode="quick"):
        await asyncio.sleep(10)

    async def fast_wait_for(awaitable, timeout):
        awaitable.cancel()
        try:
            await awaitable
        except asyncio.CancelledError:
            pass
        raise asyncio.TimeoutError

    monkeypatch.setattr("app.services.scheduler.scan_external_target", timed_out_scan)
    monkeypatch.setattr("app.services.scheduler.asyncio.wait_for", fast_wait_for)
    with session_scope() as db:
        for target in db.scalars(select(ExternalTarget)).all():
            target.enabled = False
        db.add(ExternalTarget(name="Timeout target", host="203.0.113.78", enabled=True))

    async def scenario():
        instance = ExternalScanScheduler()
        instance.update({"enabled": True, "interval_minutes": 60, "scan_mode": "quick", "target_timeout_seconds": 2})
        result = await instance.run_once()
        assert result == {"scanned": 0, "failed": 1, "cancelled": 0}
        instance.update({"enabled": False})

    asyncio.run(scenario())
    with session_scope() as db:
        history = db.scalar(select(SchedulerRun).order_by(SchedulerRun.id.desc()))
        assert history.targets_count == 1
        assert history.failed == 1
        assert history.status == "failed"


def test_scheduler_rejects_duplicate_target_claim():
    instance = ExternalScanScheduler()
    assert instance.claim_target("target-1") is True
    assert instance.claim_target("target-1") is False
    instance.release_target("target-1")
    assert instance.claim_target("target-1") is True
