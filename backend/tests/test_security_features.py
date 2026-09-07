from app.services.admin_auth import admin_auth

ADMIN_PASSWORD = "Test-Admin-Password!42"


def unlock_admin(client):
    if not client.get("/api/admin/status").json()["configured"]:
        assert client.post("/api/admin/setup", json={"password": ADMIN_PASSWORD}).status_code == 200
    return client.post("/api/admin/unlock", json={"password": ADMIN_PASSWORD})


def test_first_use_requires_user_password_and_rotation_revokes_session(client):
    status = client.get("/api/admin/status").json()
    if not status["configured"]:
        assert client.post("/api/admin/unlock", json={"password": ADMIN_PASSWORD}).status_code == 409
        assert client.post("/api/admin/setup", json={"password": "short"}).status_code == 422
        assert client.post("/api/admin/setup", json={"password": ADMIN_PASSWORD}).status_code == 200
    unlocked = unlock_admin(client).json()
    old_token = unlocked["unlock_token"]
    changed = client.post("/api/admin/setup", headers={"X-Admin-Unlock": old_token}, json={"password": ADMIN_PASSWORD})
    assert changed.status_code == 200
    assert client.put("/api/public-scan?enabled=false", headers={"X-Admin-Unlock": old_token}).status_code == 403
    assert "password" not in str(client.get("/api/admin/status").json()).lower()


def test_public_scan_requires_unlock_and_allowlist(client):
    locked = client.post("/api/public-scan/preview", json={"target_id": "missing"})
    assert locked.status_code == 403
    unlocked = unlock_admin(client)
    assert unlocked.status_code == 200
    token = unlocked.json()["unlock_token"]
    headers = {"X-Admin-Unlock": token}
    enabled = client.put("/api/public-scan?enabled=true", headers=headers)
    assert enabled.status_code == 200 and enabled.json()["enabled"] is True
    target = client.post("/api/external-targets", json={"name": "Authorized range", "host": "8.8.8.0/30", "enabled": True}).json()
    preview = client.post("/api/public-scan/preview", headers=headers, json={"target_id": target["id"]})
    assert preview.status_code == 200
    assert preview.json()["target_count"] == 2
    assert "password" not in str(client.get("/api/audit-logs").json()).lower()


def test_internet_wide_range_is_rejected(client):
    token = unlock_admin(client).json()["unlock_token"]
    target = client.post("/api/external-targets", json={"name": "Forbidden range", "host": "0.0.0.0/0", "enabled": True}).json()
    response = client.post("/api/public-scan/preview", headers={"X-Admin-Unlock": token}, json={"target_id": target["id"]})
    assert response.status_code == 400


def test_failed_admin_login_lockout(client):
    admin_auth.failures.clear(); admin_auth.locked_until = 0
    for _ in range(5):
        response = client.post("/api/admin/unlock", json={"password": "wrong-password"})
        assert response.status_code in {401, 429}
    assert client.post("/api/admin/unlock", json={"password": ADMIN_PASSWORD}).status_code == 429
    admin_auth.failures.clear(); admin_auth.locked_until = 0


def test_credential_rotation_cleans_old_blob_without_secret_response(client, monkeypatch):
    camera = client.post("/api/cameras", json={"name": "Credential camera", "ip": "192.168.250.91"}).json()
    references = iter(["dpapi-first", "dpapi-second"])
    deleted = []
    monkeypatch.setattr("app.api.routes.credential_store.put", lambda *args: next(references))
    monkeypatch.setattr("app.api.routes.credential_store.delete", lambda ref: deleted.append(ref) or True)
    first = client.put(f"/api/cameras/{camera['id']}/credentials", json={"username": "admin", "password": "secret-one", "rtsp_path": "/live"})
    second = client.put(f"/api/cameras/{camera['id']}/credentials", json={"username": "admin", "password": "secret-two", "rtsp_path": "/live"})
    assert first.json() == {"configured": True, "stream_kind": "sub"}
    assert "secret" not in second.text and "admin" not in second.text
    assert deleted == ["dpapi-first"]
    removed = client.delete(f"/api/cameras/{camera['id']}/credentials")
    assert removed.status_code == 204
    assert deleted[-1] == "dpapi-second"


def test_optional_shodan_is_non_blocking(client):
    response = client.get("/api/shodan/status")
    assert response.status_code == 200
    assert response.json()["scope"] == "authorized_allowlist_only"
