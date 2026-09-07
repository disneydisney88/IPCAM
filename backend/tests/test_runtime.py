import asyncio
from pathlib import Path

from app.media.go2rtc_manager import Go2RTCManager
from app.scanners.engine import coordinator


def test_mock_scan_emits_progress_and_completion():
    scan_id = coordinator.create("192.168.252.0/30")
    asyncio.run(coordinator.run(scan_id, mock=True))
    event_names = [item["event"] for item in coordinator.events[scan_id]]
    assert "progress" in event_names
    assert event_names[-1] == "complete"
    assert scan_id in coordinator.done


def test_go2rtc_missing_binary_health_state(tmp_path):
    manager = Go2RTCManager()
    manager.executable = tmp_path / "missing-go2rtc.exe"
    result = asyncio.run(manager.health())
    assert result["available"] is False
    assert result["message"] == "STREAM GATEWAY NOT AVAILABLE"

