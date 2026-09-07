import asyncio

from app.media.go2rtc_manager import Go2RTCManager


def test_stream_error_classification():
    assert Go2RTCManager.classify_stream_error("401 Unauthorized") == "authentication_failed"
    assert Go2RTCManager.classify_stream_error("connection timed out") == "timeout"
    assert Go2RTCManager.classify_stream_error("connection refused") == "stream_unavailable"


def test_health_monitor_restarts_after_consecutive_failures(monkeypatch):
    instance = Go2RTCManager()
    async def offline(): return {"available": True, "running": False, "state": "offline", "message": "offline"}
    monkeypatch.setattr(instance, "health", offline)
    monkeypatch.setattr(instance, "reload", lambda: True)
    async def scenario():
        first = await instance.monitor_once()
        second = await instance.monitor_once()
        assert "recovery_attempted" not in first
        assert second["recovery_attempted"] is True
        assert second["restart_count"] == 1
    asyncio.run(scenario())


def test_health_monitor_does_not_restart_when_gateway_is_healthy(monkeypatch):
    instance = Go2RTCManager()
    async def healthy(): return {"available": True, "running": True, "message": "READY"}
    monkeypatch.setattr(instance, "health", healthy)
    monkeypatch.setattr(instance, "reload", lambda: (_ for _ in ()).throw(AssertionError("unexpected restart")))
    asyncio.run(instance.monitor_once())
    assert instance.consecutive_failures == 0
