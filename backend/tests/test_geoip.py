from __future__ import annotations

import asyncio

import pytest

from app.services import geoip


@pytest.fixture(autouse=True)
def clean_geoip_state():
    geoip._reset_state()
    yield
    geoip._reset_state()


def test_private_addresses_never_leave_the_machine(monkeypatch):
    async def fail_fetch(ip):
        raise AssertionError(f"network fetch must not run for {ip}")

    monkeypatch.setattr(geoip, "_fetch", fail_fetch)
    for value in ("192.168.1.10", "10.0.0.5", "172.16.4.4", "127.0.0.1", "169.254.9.9", "224.0.0.1", "0.0.0.0"):
        result = asyncio.run(geoip.resolve_ip_location(value))
        assert result == geoip.LOCAL_RESULT


def test_private_hostname_resolves_to_lan(monkeypatch):
    async def fail_fetch(ip):
        raise AssertionError(f"network fetch must not run for {ip}")

    monkeypatch.setattr(geoip, "_fetch", fail_fetch)
    result = asyncio.run(geoip.resolve_ip_location("localhost"))
    assert result == geoip.LOCAL_RESULT


def test_public_ip_is_resolved_and_cached(monkeypatch):
    calls = []

    async def fake_fetch(ip):
        calls.append(ip)
        return {"is_private": False, "country": "United States", "city": "Mountain View",
                "latitude": 38.0055, "longitude": -122.099, "isp": "Google LLC"}

    monkeypatch.setattr(geoip, "_fetch", fake_fetch)
    first = asyncio.run(geoip.resolve_ip_location("8.8.8.8"))
    second = asyncio.run(geoip.resolve_ip_location("8.8.8.8"))
    assert calls == ["8.8.8.8"]
    assert first["city"] == "Mountain View"
    assert second == first


def test_failed_lookup_is_negative_cached(monkeypatch):
    calls = []

    async def fake_fetch(ip):
        calls.append(ip)
        return None

    monkeypatch.setattr(geoip, "_fetch", fake_fetch)
    assert asyncio.run(geoip.resolve_ip_location("9.9.9.9")) is None
    assert asyncio.run(geoip.resolve_ip_location("9.9.9.9")) is None
    assert calls == ["9.9.9.9"]


def test_unknown_hostname_fails_gracefully():
    assert asyncio.run(geoip.resolve_ip_location("nonexistent.invalid")) is None
    assert asyncio.run(geoip.resolve_ip_location("")) is None


def test_camera_geo_columns_survive_api_roundtrip(client):
    payload = {"name": "Geo Test", "ip": "203.0.113.50", "connection_type": "internet",
               "latitude": 25.0330, "longitude": 121.5654, "country": "Taiwan", "city": "Taipei", "isp": "Test ISP"}
    created = client.post("/api/cameras", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["latitude"] == 25.0330
    assert body["city"] == "Taipei"
    assert body["model_specs"]["tags"], "create_camera should enrich tags automatically"

    listed = client.get("/api/cameras").json()
    match = next(item for item in listed if item["id"] == body["id"])
    assert match["country"] == "Taiwan"
    client.delete(f"/api/cameras/{body['id']}")


def test_geoip_refresh_on_private_camera_flags_local(client):
    created = client.post("/api/cameras", json={"name": "LAN Geo", "ip": "192.168.50.10"})
    camera_id = created.json()["id"]
    result = client.post(f"/api/cameras/{camera_id}/geoip")
    assert result.status_code == 200
    assert result.json()["geoip"] == "local"
    assert result.json()["latitude"] is None
    client.delete(f"/api/cameras/{camera_id}")


def test_telemetry_reports_offline_for_closed_ports(client):
    created = client.post("/api/cameras", json={"name": "Telemetry", "ip": "127.0.0.1"})
    camera_id = created.json()["id"]
    result = client.get(f"/api/telemetry?ids={camera_id}")
    assert result.status_code == 200
    report = result.json()
    assert report[0]["id"] == camera_id
    assert report[0]["online"] is False
    assert report[0]["checked_at"]
    client.delete(f"/api/cameras/{camera_id}")


def test_telemetry_ignores_bad_ids(client):
    assert client.get("/api/telemetry?ids=abc,,zz").json() == []


def test_snapshot_endpoints_on_mock_and_missing(client):
    client.post("/api/mock/ensure")
    cameras = client.get("/api/cameras").json()
    mock_camera = next(item for item in cameras if item["is_mock"])
    refused = client.post(f"/api/cameras/{mock_camera['id']}/snapshot")
    assert refused.status_code == 200
    assert refused.json()["available"] is False
    assert client.get(f"/api/cameras/{mock_camera['id']}/snapshot.jpg").status_code == 404


def test_credential_bulk_import_matches_by_ip(client):
    created = client.post("/api/cameras", json={"name": "Cred Import", "ip": "192.168.77.10"})
    camera_id = created.json()["id"]
    content = "ip,username,password,rtsp_path,stream_kind\n"
    content += "192.168.77.10, admin, Sup3r-Secret!, /Streaming/Channels/101, main\n"
    content += "192.168.77.99, ghost, nope\n"
    result = client.post("/api/cameras/import-credentials", json={"content": content})
    assert result.status_code == 200
    body = result.json()
    assert body["matched"] == 1
    assert body["updated"] == 1
    assert len(body["errors"]) == 1 and body["errors"][0]["row"] == 3
    status = client.get(f"/api/cameras/{camera_id}/credentials").json()
    assert status["configured"] is True and "main" in status["stream_kinds"]
    specs = next(item for item in client.get("/api/cameras").json() if item["id"] == camera_id)["model_specs"]
    assert specs["rtsp_path_main"] == "/Streaming/Channels/101"
    client.delete(f"/api/cameras/{camera_id}")


def test_mock_data_carries_geo_and_spec_tags(client):
    client.post("/api/mock/ensure")
    cameras = client.get("/api/cameras").json()
    mocks = [item for item in cameras if item["is_mock"]]
    assert mocks, "mock fixtures should exist"
    assert all((item.get("model_specs") or {}).get("tags") for item in mocks)
    geo = [item for item in mocks if item["latitude"] is not None and item["longitude"] is not None]
    assert len(geo) == 3
    assert all(item["city"] and item["country"] for item in geo)
