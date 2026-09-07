from sqlalchemy import inspect

from app.database.core import engine
from app.database.migrations import migrate_database


def test_schema_contains_milestone_tables():
    tables = set(inspect(engine).get_table_names())
    assert {"cameras", "areas", "camera_groups", "camera_group_members", "favorites",
            "saved_views", "saved_view_items", "scan_sessions", "camera_streams", "settings",
            "external_targets", "audit_logs", "scheduler_runs"} <= tables


def test_baseline_migration_is_versioned_and_idempotent():
    assert migrate_database() == 5
    assert migrate_database() == 5
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 5


def test_area_favorite_and_saved_view_persist(client):
    area = client.post("/api/areas", json={"name": "Test Lobby"})
    assert area.status_code == 201
    camera = client.post("/api/cameras", json={
        "name": "Test CAM", "ip": "192.168.250.10", "mac": "00-11-22-33-44-55",
        "manufacturer": "Axis", "model": "Test Model", "area_id": area.json()["id"],
    })
    assert camera.status_code == 201
    camera_id = camera.json()["id"]

    favorite = client.put(f"/api/cameras/{camera_id}/favorite", json={"favorite": True})
    assert favorite.status_code == 200
    assert favorite.json()["favorite"] is True

    view = client.post("/api/views", json={
        "name": "Test Patrol", "grid_size": 4, "filters": {"area_id": area.json()["id"]},
        "stream_preference": "sub", "items": [{"camera_id": camera_id, "position": 0, "layout": {"x": 0, "y": 0, "w": 6, "h": 7}}],
    })
    assert view.status_code == 201
    assert view.json()["items"][0]["camera_id"] == camera_id

    reloaded = client.get("/api/cameras").json()
    saved = client.get("/api/views").json()
    assert next(item for item in reloaded if item["id"] == camera_id)["favorite"] is True
    assert next(item for item in saved if item["id"] == view.json()["id"])["grid_size"] == 4


def test_external_target_repository_persists(client):
    created = client.post("/api/external-targets", json={
        "name": "Office NVR",
        "host": "203.0.113.10",
        "port_overrides": "8554",
        "notes": "Authorized test target",
        "enabled": True,
    })
    assert created.status_code == 201
    body = created.json()
    assert body["host"] == "203.0.113.10"
    assert body["port_overrides"] == "8554"
    listed = client.get("/api/external-targets").json()
    assert any(item["id"] == body["id"] for item in listed)


def test_allowlist_csv_import_creates_updates_and_rejects(client):
    content = "name,host,port_overrides,notes,enabled\nGate,203.0.113.20,8554,Authorized,true\nBad,127.0.0.1,,,true"
    response = client.post("/api/external-targets/import", json={"format": "csv", "content": content})
    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["rejected"] == 1
    content = '[{"name":"Updated Gate","host":"203.0.113.20","enabled":false}]'
    updated = client.post("/api/external-targets/import", json={"format": "json", "content": content})
    assert updated.status_code == 200
    assert updated.json()["updated"] == 1
    target = next(item for item in client.get("/api/external-targets").json() if item["host"] == "203.0.113.20")
    assert target["name"] == "Updated Gate"
    assert target["enabled"] is False


def test_scheduler_configuration_and_audit_log(client):
    response = client.put("/api/scheduler", json={"enabled": True, "interval_minutes": 15, "scan_mode": "quick"})
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert client.get("/api/scheduler").json()["scan_mode"] == "quick"
    logs = client.get("/api/audit-logs").json()
    assert any(entry["action"] == "scheduler.updated" for entry in logs["items"])
    client.put("/api/scheduler", json={"enabled": False, "interval_minutes": 15, "scan_mode": "quick"})


def test_audit_log_pagination_filters_and_csv_export(client):
    for interval in (20, 25, 30):
        client.put("/api/scheduler", json={"enabled": False, "interval_minutes": interval, "scan_mode": "quick"})
    page = client.get("/api/audit-logs", params={"page": 1, "page_size": 2, "action": "scheduler.updated", "status": "success"})
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["pages"] >= 2
    assert all(item["action"] == "scheduler.updated" for item in body["items"])

    exported = client.get("/api/audit-logs/export.csv", params={"action": "scheduler.updated"})
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=ipcam-audit-log.csv" == exported.headers["content-disposition"]
    assert "scheduler.updated" in exported.content.decode("utf-8-sig")
    actions = client.get("/api/audit-logs/actions")
    assert actions.status_code == 200
    assert "scheduler.updated" in actions.json()
