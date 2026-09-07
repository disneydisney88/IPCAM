from __future__ import annotations

import pytest

from app.database.core import session_scope
from app.models import Setting
from app.services.admin_auth import admin_auth


PASSWORD = "lock-test-password-123"


def _reset_admin_setting() -> None:
    with session_scope() as db:
        setting = db.get(Setting, "admin_auth")
        if setting:
            setting.value = {"must_change": True, "salt": "aa", "hash": "bb"}
    admin_auth.tokens.clear()
    admin_auth.failures.clear()
    admin_auth.locked_until = 0.0


@pytest.fixture()
def lock_enabled(monkeypatch):
    monkeypatch.setenv("IPCAM_DASHBOARD_LOCK", "1")
    yield
    monkeypatch.setenv("IPCAM_DASHBOARD_LOCK", "0")
    _reset_admin_setting()


def test_setup_required_blocks_api_until_password_exists(client, lock_enabled):
    _reset_admin_setting()
    assert admin_auth.configured() is False
    blocked = client.get("/api/cameras")
    assert blocked.status_code == 428
    assert blocked.json()["detail"] == "Admin password setup required"
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/admin/status").status_code == 200

    client.post("/api/admin/setup", json={"password": PASSWORD})
    assert client.get("/api/cameras").status_code == 401
    unlocked = client.post("/api/admin/unlock", json={"password": PASSWORD})
    token = unlocked.json()["unlock_token"]
    assert client.get("/api/cameras", headers={"X-Admin-Unlock": token}).status_code == 200


def test_unlocked_token_grants_access_and_wrong_password_fails(client, lock_enabled):
    admin_auth.setup(PASSWORD)
    assert client.get("/api/cameras").status_code == 401
    wrong = client.post("/api/admin/unlock", json={"password": "totally-wrong-pass"})
    assert wrong.status_code == 401
    result = client.post("/api/admin/unlock", json={"password": PASSWORD})
    token = result.json()["unlock_token"]
    assert client.get("/api/areas", headers={"X-Admin-Unlock": token}).status_code == 200
    assert client.get("/api/telemetry?ids=", headers={"X-Admin-Unlock": token}).json() == []


def test_event_stream_and_snapshot_routes_stay_reachable(client, lock_enabled):
    admin_auth.setup(PASSWORD)
    assert client.get("/api/scans/999999/events").status_code == 404
    assert client.get("/api/cameras/999999/snapshot.jpg").status_code == 404


def test_lock_disabled_by_default_in_suite(client):
    assert client.get("/api/cameras").status_code == 200
