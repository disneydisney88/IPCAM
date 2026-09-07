"""Snapshot capture and caching for cameras.

Fetches one JPEG frame from the camera's HTTP snapshot endpoint (brand
specific candidates first, generic fallbacks after), using the stored
per-stream credentials when available with digest then basic
authentication. Frames are cached under the runtime snapshots directory and
served by the API; ``snapshot_url`` on the camera row points at the API
route so the browser never talks to the camera directly.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.scanners.fingerprints import FINGERPRINT_DATABASE
from app.services.credentials import credential_store

GENERIC_SNAPSHOT_PATHS = [
    "/ISAPI/Streaming/channels/101/picture",
    "/cgi-bin/snapshot.cgi",
    "/onvif-http/snapshot",
    "/axis-cgi/jpg/image.cgi",
    "/snapshot.jpg",
]
CAPTURE_TIMEOUT_SECONDS = 4.0


def snapshot_path(camera_id: int) -> Path:
    return settings.snapshots_dir / f"camera-{camera_id}.jpg"


def snapshot_url(camera_id: int, version: int | str | None = None) -> str:
    stamp = version if version is not None else int(time.time())
    return f"/api/cameras/{camera_id}/snapshot.jpg?v={stamp}"


def _brand_candidates(manufacturer: str | None) -> list[str]:
    brand = (manufacturer or "").lower()
    for key, signature in FINGERPRINT_DATABASE.items():
        if key in brand or (signature.brand_name.split(" ")[0].lower() in brand and brand):
            return signature.snapshot_endpoints
    return []


def stored_credentials(camera: Any) -> tuple[str, str] | None:
    for stream in getattr(camera, "streams", []) or []:
        if stream.rtsp_uri_secret_ref:
            credentials = credential_store.get(stream.rtsp_uri_secret_ref)
            if credentials:
                return credentials
    return None


async def capture(camera: Any) -> dict[str, Any]:
    """Capture and cache a snapshot; never raises, returns a status dict."""
    if getattr(camera, "is_mock", False):
        return {"available": False, "message": "Mock cameras have no live snapshot"}
    host = camera.host or camera.ip
    port = camera.http_port or 80
    candidates = _brand_candidates(camera.manufacturer) or GENERIC_SNAPSHOT_PATHS
    credentials = stored_credentials(camera)
    username, password = credentials if credentials else (None, None)
    last_error = "No snapshot endpoint answered"
    async with httpx.AsyncClient(verify=False, timeout=CAPTURE_TIMEOUT_SECONDS) as client:
        for path in candidates:
            url = f"http://{host}:{port}{path}"
            try:
                response = await client.get(url, auth=httpx.DigestAuth(username, password) if username else None)
                if response.status_code == 401 and username:
                    response = await client.get(url, auth=(username, password))
                content_type = response.headers.get("content-type", "")
                if response.status_code == 200 and "image" in content_type:
                    target = snapshot_path(camera.id)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(response.content)
                    return {
                        "available": True,
                        "bytes": len(response.content),
                        "snapshot_url": snapshot_url(camera.id, int(time.time())),
                    }
                last_error = f"{url} answered {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
    return {"available": False, "message": last_error}
