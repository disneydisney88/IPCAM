from app.services.credentials import WindowsCredentialStore


def test_credential_store_uses_opaque_reference_and_round_trips(tmp_path, monkeypatch):
    store = WindowsCredentialStore(tmp_path)
    monkeypatch.setattr(store, "_protect", lambda value: b"protected:" + value[::-1])
    monkeypatch.setattr(store, "_unprotect", lambda value: value.removeprefix(b"protected:")[::-1])
    reference = store.put("camera-1-sub", "operator", "not-plaintext")
    assert reference.startswith("dpapi-")
    assert "operator" not in reference and "not-plaintext" not in reference
    assert store.get(reference) == ("operator", "not-plaintext")
    persisted = (tmp_path / f"{reference}.bin").read_bytes()
    assert b"not-plaintext" not in persisted


def test_live_endpoint_has_clear_gateway_fallback(client, monkeypatch):
    async def unavailable():
        return {"available": False, "running": False, "message": "STREAM GATEWAY NOT AVAILABLE"}

    monkeypatch.setattr("app.api.routes.manager.health", unavailable)
    camera = client.post("/api/cameras", json={"name": "Live fallback", "ip": "192.168.250.80"}).json()
    response = client.get(f"/api/cameras/{camera['id']}/live")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["state"] == "gateway_unavailable"
    assert body["player_url"] is None
