from __future__ import annotations

import asyncio
import csv
import io
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import (
    AdminPasswordInput, AllowlistImportInput, AreaInput, CameraCredentialInput, CameraInput, CameraUpdate, ExternalScanInput, ExternalTargetInput,
    FavoriteInput, GroupInput, GroupMembersInput, PublicScanInput, SavedViewInput, ScanInput, SchedulerUpdateInput, ShodanKeyInput,
)
from app.database.core import get_db, session_scope
from app.media.go2rtc_manager import manager
from app.models import (
    Area, AuditLog, Camera, CameraGroup, CameraGroupMember, CameraStream, ExternalTarget, Favorite, SavedView,
    SavedViewItem, SchedulerRun, ScanSession, Setting,
)
from app.scanners.engine import coordinator
from app.scanners.external import scan_external_target
from app.services.allowlist import parse_allowlist
from app.services.admin_auth import admin_auth
from app.services.audit import record_audit
from app.services.credentials import credential_store
from app.services.geoip import resolve_ip_location
from app.services.scheduler import scheduler
from app.services.public_scan import public_scanner
from app.services.identity import camera_identity, normalize_mac
from app.services.network import detect_interfaces, validate_private_cidr
from app.services.snapshots import capture as capture_snapshot
from app.services.snapshots import snapshot_path
from app.services.specs import spec_enricher


router = APIRouter(prefix="/api")


def stream_to_dict(stream: CameraStream) -> dict[str, Any]:
    return {
        "id": stream.id, "kind": stream.kind, "codec": stream.codec, "width": stream.width,
        "height": stream.height, "fps": stream.fps, "bitrate": stream.bitrate,
        "audio_codec": stream.audio_codec, "latency_ms": stream.latency_ms,
        "validated": stream.validated,
    }


def camera_to_dict(camera: Camera) -> dict[str, Any]:
    return {
        "id": camera.id, "name": camera.name, "ip": camera.ip, "mac": camera.mac,
        "hostname": camera.hostname, "manufacturer": camera.manufacturer, "model": camera.model,
        "firmware": camera.firmware, "status": camera.status, "area_id": camera.area_id,
        "area_name": camera.area.name if camera.area else None, "favorite": camera.favorite is not None,
        "connection_type": camera.connection_type, "host": camera.host, "resolved_ip": camera.resolved_ip,
        "snapshot_url": camera.snapshot_url, "model_specs": camera.model_specs, "sort_order": camera.sort_order,
        "latitude": camera.latitude, "longitude": camera.longitude,
        "country": camera.country, "city": camera.city, "isp": camera.isp,
        "ptz_support": camera.ptz_support, "audio_support": camera.audio_support,
        "last_seen": camera.last_seen, "last_successful_stream": camera.last_successful_stream,
        "last_error": camera.last_error, "is_mock": camera.is_mock,
        "groups": [membership.group.name for membership in camera.group_memberships],
        "streams": [stream_to_dict(stream) for stream in camera.streams],
    }


def external_target_to_dict(target: ExternalTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "name": target.name,
        "host": target.host,
        "port_overrides": target.port_overrides,
        "enabled": target.enabled,
        "notes": target.notes,
        "last_scan": target.last_scan,
        "latitude": target.latitude,
        "longitude": target.longitude,
        "country": target.country,
        "city": target.city,
        "created_at": target.created_at,
    }


def audit_to_dict(entry: AuditLog) -> dict[str, Any]:
    return {"id": entry.id, "action": entry.action, "status": entry.status, "target_id": entry.target_id,
            "target_name": entry.target_name, "details": entry.details, "created_at": entry.created_at}


def view_to_dict(view: SavedView) -> dict[str, Any]:
    return {
        "id": view.id, "name": view.name, "grid_size": view.grid_size, "filters": view.filters,
        "stream_preference": view.stream_preference,
        "items": [{"camera_id": item.camera_id, "position": item.position, "layout": item.layout} for item in view.items],
    }


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "ipcam-backend", "go2rtc": await manager.ensure_healthy()}


@router.get("/system/network/interfaces")
def network_interfaces() -> list[dict[str, Any]]:
    return detect_interfaces()


@router.get("/dashboard/summary")
async def dashboard_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    cameras = list(db.scalars(select(Camera)).all())
    last_scan = db.scalar(select(ScanSession).order_by(ScanSession.started_at.desc()).limit(1))
    recent_runs = db.scalars(select(SchedulerRun).order_by(SchedulerRun.started_at.desc()).limit(5)).all()
    recent_discoveries = sorted(cameras, key=lambda item: item.created_at, reverse=True)[:5]
    recent_offline = sorted((item for item in cameras if item.status == "OFFLINE"), key=lambda item: item.updated_at, reverse=True)[:5]
    return {"total_cameras": len(cameras), "online": sum(item.status == "LIVE" for item in cameras),
            "offline": sum(item.status == "OFFLINE" for item in cameras),
            "last_scan": last_scan.started_at if last_scan else None, "scheduler": scheduler.status(),
            "public_scan": public_scanner.status, "go2rtc": await manager.ensure_healthy(),
            "recent_discoveries": [camera_to_dict(item) for item in recent_discoveries],
            "recent_offline": [camera_to_dict(item) for item in recent_offline],
            "recent_scan_jobs": [{"id": item.id, "status": item.status, "started_at": item.started_at} for item in recent_runs]}


@router.get("/admin/status")
def admin_status() -> dict[str, Any]:
    return admin_auth.status()


@router.post("/admin/setup")
def admin_setup(payload: AdminPasswordInput, x_admin_unlock: str | None = Header(default=None)) -> dict[str, bool]:
    if admin_auth.configured():
        try: admin_auth.require(x_admin_unlock)
        except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    admin_auth.setup(payload.password)
    return {"configured": True}


@router.post("/admin/unlock")
def admin_unlock(payload: AdminPasswordInput) -> dict[str, Any]:
    try: token = admin_auth.unlock(payload.password)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(429 if "locked" in message else 409 if "not configured" in message else 401, message) from exc
    return {"unlock_token": token, "expires_in": admin_auth.SESSION_TTL_SECONDS}


def _public_config(db: Session) -> dict[str, Any]:
    setting = db.get(Setting, "public_scan")
    return {"enabled": False, **(setting.value if setting else {})}


@router.get("/public-scan")
def public_scan_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {**_public_config(db), **public_scanner.status, "admin_configured": admin_auth.configured()}


@router.put("/public-scan")
def configure_public_scan(enabled: bool, x_admin_unlock: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    try: admin_auth.require(x_admin_unlock)
    except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    setting = db.get(Setting, "public_scan")
    value = {"enabled": enabled}
    if setting: setting.value = value
    else: db.add(Setting(key="public_scan", value=value))
    record_audit(db, "public_scan.configured", details={"enabled": enabled, "operator": "admin"})
    db.commit()
    return {**value, **public_scanner.status}


@router.post("/public-scan/preview")
def preview_public_scan(payload: PublicScanInput, x_admin_unlock: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    try: admin_auth.require(x_admin_unlock)
    except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    target = db.get(ExternalTarget, payload.target_id)
    if not target or not target.enabled: raise HTTPException(400, "Target must be enabled in Authorized Allowlist")
    try: targets = public_scanner.expand(target.host)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    return {"target_id": target.id, "target_range": target.host, "target_count": len(targets),
            "rate_limit": payload.rate_limit, "concurrency": payload.concurrency, "timeout_seconds": payload.timeout_seconds}


@router.post("/public-scan/start", status_code=202)
def start_public_scan(payload: PublicScanInput, background_tasks: BackgroundTasks,
                      x_admin_unlock: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    try: admin_auth.require(x_admin_unlock)
    except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    if not _public_config(db)["enabled"]: raise HTTPException(403, "Public Scan is disabled")
    target = db.get(ExternalTarget, payload.target_id)
    if not target or not target.enabled: raise HTTPException(400, "Target must be enabled in Authorized Allowlist")
    try: targets = public_scanner.expand(target.host)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    record_audit(db, "public_scan.started", target_id=target.id, target_name=target.name,
                 details={"target_range": target.host, "target_count": len(targets), "operator": "admin"})
    db.commit()
    background_tasks.add_task(public_scanner.run, targets, payload.rate_limit, payload.concurrency, payload.timeout_seconds)
    return {"state": "queued", "target_count": len(targets)}


@router.post("/public-scan/stop")
def stop_public_scan(x_admin_unlock: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    try: admin_auth.require(x_admin_unlock)
    except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    public_scanner.stop()
    record_audit(db, "public_scan.stopped", details={"operator": "admin", "checked": public_scanner.status["checked"]})
    db.commit()
    return public_scanner.status


@router.get("/shodan/status")
def shodan_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    setting = db.get(Setting, "shodan_api_key")
    configured = bool(setting and setting.value.get("credential_ref"))
    return {"configured": configured, "status": "ready" if configured else "not_configured",
            "enabled": configured, "scope": "authorized_allowlist_only"}


@router.put("/shodan/key")
def set_shodan_key(payload: ShodanKeyInput, x_admin_unlock: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, bool]:
    try: admin_auth.require(x_admin_unlock)
    except ValueError as exc: raise HTTPException(403, str(exc)) from exc
    setting = db.get(Setting, "shodan_api_key")
    old_reference = setting.value.get("credential_ref") if setting else None
    reference = credential_store.put("shodan-api", "shodan", payload.api_key)
    if setting: setting.value = {"credential_ref": reference}
    else: db.add(Setting(key="shodan_api_key", value={"credential_ref": reference}))
    db.commit()
    if old_reference: credential_store.delete(old_reference)
    record_audit(db, "shodan.key_updated", details={"operator": "admin"})
    db.commit()
    return {"configured": True}


@router.get("/shodan/enrich/{target_id}")
async def shodan_enrich(target_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    target = db.get(ExternalTarget, target_id)
    if not target or not target.enabled: raise HTTPException(400, "Target must be enabled in Authorized Allowlist")
    setting = db.get(Setting, "shodan_api_key")
    credentials = credential_store.get(setting.value.get("credential_ref")) if setting else None
    if not credentials: return {"configured": False, "source": "shodan", "results": []}
    targets = public_scanner.expand(target.host)
    if len(targets) > 32: raise HTTPException(400, "Shodan enrichment is limited to 32 allowlisted IPs per request")
    api_key = credentials[1]
    import httpx
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for host in targets:
            response = await client.get(f"https://api.shodan.io/shodan/host/{host}", params={"key": api_key})
            if response.status_code == 200:
                data = response.json()
                results.append({"source": "shodan", "ip": host, "ports": data.get("ports", []),
                                "organization": data.get("org"), "hostnames": data.get("hostnames", []),
                                "last_update": data.get("last_update")})
    record_audit(db, "shodan.enriched", target_id=target.id, target_name=target.name,
                 details={"operator": "admin", "target_range": target.host, "results": len(results)})
    db.commit()
    return {"configured": True, "source": "shodan", "results": results}


@router.get("/cameras")
def list_cameras(area_id: int | None = None, favorite: bool = False, search: str = "", db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    statement = select(Camera).order_by(Camera.sort_order, Camera.name, Camera.id)
    if area_id is not None:
        statement = statement.where(Camera.area_id == area_id)
    if favorite:
        statement = statement.join(Favorite)
    if search.strip():
        value = f"%{search.strip()}%"
        statement = statement.where((Camera.name.ilike(value)) | (Camera.ip.ilike(value)) | (Camera.model.ilike(value)))
    return [camera_to_dict(camera) for camera in db.scalars(statement).unique().all()]


@router.post("/cameras", status_code=201)
def create_camera(payload: CameraInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    identity = camera_identity(mac=payload.mac, onvif_uuid=payload.onvif_uuid, serial=payload.serial,
                               manufacturer=payload.manufacturer, model=payload.model, ip=payload.ip)
    values = payload.model_dump()
    values["mac"] = normalize_mac(payload.mac)
    values["host"] = values.get("host") or values["ip"]
    values["resolved_ip"] = values.get("resolved_ip") or values["ip"]
    if not (values.get("model_specs") or {}).get("tags"):
        enriched = spec_enricher.enrich(payload.manufacturer, payload.model)
        specs = values.get("model_specs") or {}
        specs.setdefault("tags", enriched.get("tags") or [])
        if enriched.get("resolution_mp"):
            specs.setdefault("resolution_mp", enriched["resolution_mp"])
        values["model_specs"] = specs
    camera = Camera(**values, identity_key=identity, status="NEW")
    db.add(camera)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Camera identity already exists") from exc
    db.refresh(camera)
    return camera_to_dict(camera)


@router.patch("/cameras/{camera_id}")
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return camera_to_dict(camera)


@router.put("/cameras/{camera_id}/credentials")
def set_camera_credentials(camera_id: int, payload: CameraCredentialInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    reference = credential_store.put(f"camera-{camera_id}-{payload.stream_kind}", payload.username, payload.password)
    stream = db.scalar(select(CameraStream).where(CameraStream.camera_id == camera_id, CameraStream.kind == payload.stream_kind))
    old_reference = stream.rtsp_uri_secret_ref if stream else None
    if not stream:
        stream = CameraStream(camera_id=camera_id, kind=payload.stream_kind)
        db.add(stream)
    stream.rtsp_uri_secret_ref = reference
    specs = dict(camera.model_specs or {})
    specs[f"rtsp_path_{payload.stream_kind}"] = payload.rtsp_path
    camera.model_specs = specs
    db.commit()
    if old_reference and old_reference != reference:
        credential_store.delete(old_reference)
    record_audit(db, "camera.credentials_updated", target_id=str(camera_id), target_name=camera.name,
                 details={"stream_kind": payload.stream_kind})
    db.commit()
    return {"configured": True, "stream_kind": payload.stream_kind}


@router.get("/cameras/{camera_id}/credentials")
def camera_credential_status(camera_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not db.get(Camera, camera_id): raise HTTPException(404, "Camera not found")
    kinds = list(db.scalars(select(CameraStream.kind).where(CameraStream.camera_id == camera_id, CameraStream.rtsp_uri_secret_ref.is_not(None))).all())
    return {"configured": bool(kinds), "stream_kinds": kinds}


@router.delete("/cameras/{camera_id}/credentials", status_code=204)
def delete_camera_credentials(camera_id: int, kind: str = Query(default="sub", pattern="^(main|sub)$"), db: Session = Depends(get_db)) -> None:
    camera = db.get(Camera, camera_id)
    if not camera: raise HTTPException(404, "Camera not found")
    stream = db.scalar(select(CameraStream).where(CameraStream.camera_id == camera_id, CameraStream.kind == kind))
    if stream and stream.rtsp_uri_secret_ref:
        reference = stream.rtsp_uri_secret_ref
        stream.rtsp_uri_secret_ref = None
        db.commit()
        credential_store.delete(reference)
        manager.remove_stream(camera_id, kind)
    record_audit(db, "camera.credentials_deleted", target_id=str(camera_id), target_name=camera.name, details={"stream_kind": kind})
    db.commit()


@router.get("/cameras/{camera_id}/live")
async def camera_live(camera_id: int, kind: str = Query(default="sub", pattern="^(main|sub)$"),
                      db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    health = await manager.health()
    if not health["available"]:
        return {"available": False, "state": "gateway_unavailable", "message": health["message"], "player_url": None}
    stream = db.scalar(select(CameraStream).where(CameraStream.camera_id == camera_id, CameraStream.kind == kind))
    if not stream or not stream.rtsp_uri_secret_ref:
        return {"available": False, "state": "credentials_required", "message": "RTSP credentials are not configured", "player_url": None}
    credentials = credential_store.get(stream.rtsp_uri_secret_ref)
    if not credentials:
        return {"available": False, "state": "credential_unavailable", "message": "Stored credentials are unavailable", "player_url": None}
    username, password = credentials
    host = camera.host or camera.ip
    path = (camera.model_specs or {}).get(f"rtsp_path_{kind}", "/")
    from urllib.parse import quote
    uri = f"rtsp://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{camera.rtsp_port or 554}{path}"
    stream_name = manager.register_stream(camera.id, uri, kind)
    if not health["running"]:
        manager.reload()
    return {"available": True, "state": "ready", "message": "READY", "player_url": manager.player_url(stream_name)}


@router.post("/cameras/{camera_id}/snapshot")
async def capture_camera_snapshot(camera_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    result = await capture_snapshot(camera)
    if result.get("available"):
        camera.snapshot_url = result["snapshot_url"]
        db.commit()
    return result


@router.get("/cameras/{camera_id}/snapshot.jpg")
def serve_camera_snapshot(camera_id: int) -> FileResponse:
    path = snapshot_path(camera_id)
    if not path.exists():
        raise HTTPException(404, "Snapshot has not been captured yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/cameras/{camera_id}/geoip")
async def refresh_camera_geoip(camera_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    location = await resolve_ip_location(camera.resolved_ip or camera.ip)
    if location is None:
        return camera_to_dict(camera) | {"geoip": "unresolved"}
    if not location.get("is_private"):
        camera.latitude = location.get("latitude")
        camera.longitude = location.get("longitude")
        camera.country = location.get("country")
        camera.city = location.get("city")
        camera.isp = location.get("isp")
        record_audit(db, "camera.geoip_updated", target_id=str(camera.id), target_name=camera.name,
                     details={"city": camera.city, "country": camera.country})
        db.commit()
        db.refresh(camera)
    return camera_to_dict(camera) | {"geoip": "local" if location.get("is_private") else "resolved"}


@router.post("/cameras/{camera_id}/enrich-specs")
def enrich_camera_specs(camera_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    enriched = spec_enricher.enrich(camera.manufacturer, camera.model)
    specs = dict(camera.model_specs or {})
    specs.update({key: value for key, value in enriched.items() if key != "model"})
    specs.setdefault("tags", enriched.get("tags") or [])
    camera.model_specs = specs
    db.commit()
    db.refresh(camera)
    return camera_to_dict(camera)


@router.get("/telemetry")
async def camera_telemetry(ids: str = Query(default=""), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    id_list = []
    for value in ids.split(","):
        value = value.strip()
        if value.isdigit() and int(value) not in id_list:
            id_list.append(int(value))
    id_list = id_list[:64]
    if not id_list:
        return []
    cameras = db.scalars(select(Camera).where(Camera.id.in_(id_list))).all()
    checked_at = datetime.now(timezone.utc).isoformat()

    async def probe(camera: Camera) -> dict[str, Any]:
        if camera.is_mock:
            return {"id": camera.id, "online": camera.status == "LIVE", "latency_ms": None, "checked_at": checked_at}
        host = camera.host or camera.ip
        ports = [port for port in (camera.rtsp_port, camera.http_port, 554, 80) if port]
        started = time.perf_counter()
        for port in dict.fromkeys(ports):
            if await _tcp_probe(host, port):
                return {"id": camera.id, "online": True,
                        "latency_ms": round((time.perf_counter() - started) * 1000, 1), "checked_at": checked_at}
        return {"id": camera.id, "online": False, "latency_ms": None, "checked_at": checked_at}

    return list(await asyncio.gather(*(probe(camera) for camera in cameras)))


async def _tcp_probe(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


@router.get("/external-targets")
def list_external_targets(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    statement = select(ExternalTarget).order_by(ExternalTarget.name)
    return [external_target_to_dict(target) for target in db.scalars(statement).all()]


@router.post("/external-targets", status_code=201)
def create_external_target(payload: ExternalTargetInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    target = ExternalTarget(
        name=payload.name.strip(),
        host=payload.host.strip(),
        port_overrides=payload.port_overrides.strip() if payload.port_overrides else None,
        notes=payload.notes.strip() if payload.notes else None,
        enabled=payload.enabled,
    )
    db.add(target)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "External target already exists") from exc
    db.refresh(target)
    record_audit(db, "allowlist.target_created", target_id=target.id, target_name=target.name,
                 details={"host": target.host, "enabled": target.enabled})
    db.commit()
    return external_target_to_dict(target)


@router.post("/external-targets/import")
def import_external_targets(payload: AllowlistImportInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        targets, errors = parse_allowlist(payload.content, payload.format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    created = updated = 0
    for item in targets:
        target = db.scalar(select(ExternalTarget).where(ExternalTarget.host == item.host.strip()))
        values = {
            "name": item.name.strip(), "port_overrides": item.port_overrides.strip() if item.port_overrides else None,
            "notes": item.notes.strip() if item.notes else None, "enabled": item.enabled,
        }
        if target:
            for key, value in values.items():
                setattr(target, key, value)
            updated += 1
        else:
            db.add(ExternalTarget(host=item.host.strip(), **values))
            created += 1
    record_audit(db, "allowlist.imported", "partial" if errors else "success",
                 details={"format": payload.format, "created": created, "updated": updated, "rejected": len(errors)})
    db.commit()
    return {"created": created, "updated": updated, "rejected": len(errors), "errors": errors}


@router.post("/external-targets/scan")
async def scan_external_target_endpoint(payload: ExternalScanInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    target = None
    if payload.target_id:
        target = db.get(ExternalTarget, payload.target_id)
        if not target:
            raise HTTPException(404, "External target not found")
        if not target.enabled:
            raise HTTPException(400, "External target is disabled")
    target_name = payload.name or (target.name if target else "External target")
    host = payload.host or (target.host if target else None)
    if not host:
        raise HTTPException(400, "Target host is required")
    target_value = host
    if target and target.port_overrides:
        target_value = f"{host}:{target.port_overrides}"
    elif payload.port_overrides:
        target_value = f"{host}:{payload.port_overrides}"
    target_key = str(target.id) if target else f"manual:{host}"
    if not scheduler.claim_target(target_key):
        raise HTTPException(409, "Target already has an active scan")
    try:
        result = await scan_external_target(target_value, mode=payload.mode)
    except ValueError as exc:
        record_audit(db, "external_scan.manual", "failed", target_id=target.id if target else None,
                     target_name=target_name, details={"host": host, "mode": payload.mode, "error": str(exc)})
        db.commit()
        raise HTTPException(400, str(exc)) from exc
    finally:
        scheduler.release_target(target_key)
    if target:
        target.last_scan = datetime.now(timezone.utc)
    location = await resolve_ip_location(result.get("resolved_ip") or host) if result.get("resolved_ip") else None
    result["location"] = location
    if target and location and not location.get("is_private"):
        target.latitude = location.get("latitude")
        target.longitude = location.get("longitude")
        target.country = location.get("country")
        target.city = location.get("city")
    record_audit(db, "external_scan.manual", target_id=target.id if target else None,
                 target_name=target_name, details={"host": host, "mode": payload.mode,
                                                   "geo": None if not location else location.get("city")})
    db.commit()
    return {"name": target_name, **result}


@router.get("/scheduler")
def scheduler_status() -> dict[str, Any]:
    return scheduler.status()


@router.put("/scheduler")
def update_scheduler(payload: SchedulerUpdateInput) -> dict[str, Any]:
    return scheduler.update(payload.model_dump())


@router.post("/scheduler/run")
async def run_scheduler_now() -> dict[str, int]:
    return await scheduler.run_once()


@router.post("/scheduler/stop")
async def stop_scheduler_run() -> dict[str, Any]:
    return await scheduler.cancel_run()


@router.get("/scheduler/runs")
def scheduler_runs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    runs = db.scalars(select(SchedulerRun).order_by(SchedulerRun.started_at.desc(), SchedulerRun.id.desc()).limit(limit)).all()
    return [{"id": run.id, "status": run.status, "started_at": run.started_at, "completed_at": run.completed_at,
             "targets_count": run.targets_count, "succeeded": run.succeeded, "failed": run.failed,
             "cancelled": run.cancelled, "duration_seconds": run.duration_seconds} for run in runs]


def _audit_filters(statement, date_from: datetime | None, date_to: datetime | None,
                   action: str | None, status: str | None):
    if date_from:
        statement = statement.where(AuditLog.created_at >= date_from)
    if date_to:
        statement = statement.where(AuditLog.created_at <= date_to)
    if action:
        statement = statement.where(AuditLog.action == action)
    if status:
        statement = statement.where(AuditLog.status == status)
    return statement


@router.get("/audit-logs")
def list_audit_logs(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                    date_from: datetime | None = None, date_to: datetime | None = None,
                    action: str | None = None, status: str | None = None,
                    db: Session = Depends(get_db)) -> dict[str, Any]:
    filtered = _audit_filters(select(AuditLog), date_from, date_to, action, status)
    total = db.scalar(_audit_filters(select(func.count(AuditLog.id)), date_from, date_to, action, status)) or 0
    entries = db.scalars(filtered.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                         .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [audit_to_dict(entry) for entry in entries], "page": page,
            "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@router.get("/audit-logs/export.csv")
def export_audit_logs(date_from: datetime | None = None, date_to: datetime | None = None,
                      action: str | None = None, status: str | None = None,
                      db: Session = Depends(get_db)) -> StreamingResponse:
    statement = _audit_filters(select(AuditLog), date_from, date_to, action, status)
    statement = statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).execution_options(yield_per=500)

    def generate():
        yield b"\xef\xbb\xbf"
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["id", "created_at", "action", "status", "target_id", "target_name", "details"])
        yield output.getvalue().encode("utf-8")
        for entry in db.scalars(statement):
            output.seek(0); output.truncate(0)
            writer.writerow([entry.id, entry.created_at.isoformat(), entry.action, entry.status,
                             entry.target_id or "", entry.target_name or "", json.dumps(entry.details, ensure_ascii=False)])
            yield output.getvalue().encode("utf-8")

    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=ipcam-audit-log.csv"})


@router.get("/audit-logs/actions")
def audit_actions(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)).all())


@router.delete("/external-targets/{target_id}", status_code=204)
def delete_external_target(target_id: str, db: Session = Depends(get_db)) -> None:
    target = db.get(ExternalTarget, target_id)
    if not target:
        raise HTTPException(404, "External target not found")
    db.delete(target)
    db.commit()


@router.delete("/cameras/{camera_id}", status_code=204)
def delete_camera(camera_id: int, db: Session = Depends(get_db)) -> None:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    db.delete(camera)
    db.commit()


@router.put("/cameras/{camera_id}/favorite")
def set_favorite(camera_id: int, payload: FavoriteInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(404, "Camera not found")
    favorite = db.scalar(select(Favorite).where(Favorite.camera_id == camera_id))
    if payload.favorite and not favorite:
        db.add(Favorite(camera_id=camera_id))
    elif not payload.favorite and favorite:
        db.delete(favorite)
    db.commit()
    db.refresh(camera)
    return camera_to_dict(camera)


@router.get("/areas")
def list_areas(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": area.id, "name": area.name, "camera_count": len(area.cameras)} for area in db.scalars(select(Area).order_by(Area.name)).all()]


@router.post("/areas", status_code=201)
def create_area(payload: AreaInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    area = Area(name=payload.name.strip())
    db.add(area)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Area name already exists") from exc
    db.refresh(area)
    return {"id": area.id, "name": area.name, "camera_count": 0}


@router.patch("/areas/{area_id}")
def rename_area(area_id: int, payload: AreaInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(404, "Area not found")
    area.name = payload.name.strip()
    db.commit()
    return {"id": area.id, "name": area.name, "camera_count": len(area.cameras)}


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: int, db: Session = Depends(get_db)) -> None:
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(404, "Area not found")
    for camera in area.cameras:
        camera.area_id = None
    db.delete(area)
    db.commit()


@router.get("/groups")
def list_groups(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": group.id, "name": group.name, "camera_ids": [member.camera_id for member in group.members]}
            for group in db.scalars(select(CameraGroup).order_by(CameraGroup.name)).all()]


@router.post("/groups", status_code=201)
def create_group(payload: GroupInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    group = CameraGroup(name=payload.name.strip())
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"id": group.id, "name": group.name, "camera_ids": []}


@router.put("/groups/{group_id}/members")
def replace_group_members(group_id: int, payload: GroupMembersInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    group = db.get(CameraGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    db.execute(delete(CameraGroupMember).where(CameraGroupMember.group_id == group_id))
    for camera_id in dict.fromkeys(payload.camera_ids):
        if db.get(Camera, camera_id):
            db.add(CameraGroupMember(group_id=group_id, camera_id=camera_id))
    db.commit()
    return {"id": group.id, "name": group.name, "camera_ids": payload.camera_ids}


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)) -> None:
    group = db.get(CameraGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    db.delete(group)
    db.commit()


@router.get("/views")
def list_views(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [view_to_dict(view) for view in db.scalars(select(SavedView).order_by(SavedView.name)).unique().all()]


@router.post("/views", status_code=201)
def create_view(payload: SavedViewInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    view = SavedView(name=payload.name.strip(), grid_size=payload.grid_size, filters=payload.filters,
                     stream_preference=payload.stream_preference)
    db.add(view)
    db.flush()
    for item in payload.items:
        if db.get(Camera, item.camera_id):
            db.add(SavedViewItem(view_id=view.id, **item.model_dump()))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Saved view name already exists") from exc
    db.refresh(view)
    return view_to_dict(view)


@router.put("/views/{view_id}")
def update_view(view_id: int, payload: SavedViewInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    view = db.get(SavedView, view_id)
    if not view:
        raise HTTPException(404, "Saved view not found")
    view.name, view.grid_size, view.filters = payload.name.strip(), payload.grid_size, payload.filters
    view.stream_preference = payload.stream_preference
    db.execute(delete(SavedViewItem).where(SavedViewItem.view_id == view_id))
    for item in payload.items:
        if db.get(Camera, item.camera_id):
            db.add(SavedViewItem(view_id=view_id, **item.model_dump()))
    db.commit()
    db.refresh(view)
    return view_to_dict(view)


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: int, db: Session = Depends(get_db)) -> None:
    view = db.get(SavedView, view_id)
    if not view:
        raise HTTPException(404, "Saved view not found")
    db.delete(view)
    db.commit()


@router.post("/scans", status_code=202)
async def start_scan(payload: ScanInput, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        validate_private_cidr(payload.cidr)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    scan_id = coordinator.create(payload.cidr)
    background_tasks.add_task(coordinator.run, scan_id, payload.mock)
    return {"id": scan_id, "events_url": f"/api/scans/{scan_id}/events"}


@router.get("/scans/{scan_id}")
def scan_status(scan_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    scan = db.get(ScanSession, scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")
    return {"id": scan.id, "cidr": scan.cidr, "status": scan.status, "checked": scan.checked,
            "total": scan.total, "candidates": scan.candidates, "onvif": scan.onvif_count,
            "streams": scan.streams_found, "error": scan.error}


@router.get("/scans/{scan_id}/events")
async def scan_events(scan_id: int) -> StreamingResponse:
    if scan_id not in coordinator.events:
        raise HTTPException(404, "Scan not found")

    async def generate():
        cursor = 0
        idle = 0
        while True:
            events = coordinator.events.get(scan_id, [])
            while cursor < len(events):
                item = events[cursor]
                cursor += 1
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
                idle = 0
            if scan_id in coordinator.done and cursor >= len(events):
                break
            idle += 1
            if idle % 50 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/media/health")
async def media_health() -> dict[str, Any]:
    health = await manager.health()
    return {**health, "monitoring": bool(manager.monitor_task and not manager.monitor_task.done()),
            "restart_count": manager.restarts}


@router.post("/mock/ensure")
def ensure_mock_data(db: Session = Depends(get_db)) -> dict[str, int]:
    area_names = ["Entrance", "Tower A", "Tower B", "External"]
    areas: dict[str, Area] = {}
    for name in area_names:
        area = db.scalar(select(Area).where(Area.name == name))
        if not area:
            area = Area(name=name)
            db.add(area)
            db.flush()
        areas[name] = area
    fixtures = [
        ("CAM 01", "Hikvision", "DS-2CD2146G2-I", "192.168.1.101", "Entrance", "LIVE", "H264", 1920, 1080),
        ("CAM 02", "Dahua", "IPC-HDW5442TM", "192.168.1.102", "Entrance", "LIVE", "H265", 2560, 1440),
        ("CAM 03", "Axis", "P3245-LVE", "192.168.1.103", "Tower A", "LIVE", "H264", 1920, 1080),
        ("CAM 04", "Reolink", "RLC-811A", "192.168.1.104", "Tower A", "OFFLINE", "H265", 3840, 2160),
        ("CAM 05", "Hikvision", "DS-2CD2387G2", "192.168.1.105", "Tower A", "LIVE", "H265", 3840, 2160),
        ("CAM 06", "Generic ONVIF", "ONVIF-S", "192.168.1.106", "Tower B", "AUTH REQUIRED", "H264", 1280, 720),
        ("CAM 07", "Dahua", "IPC-HFW3849T1", "192.168.1.107", "Tower B", "LIVE", "H265", 3840, 2160),
        ("CAM 08", "Axis", "M3085-V", "192.168.1.108", "Tower B", "STREAM ERROR", "H264", 1920, 1080),
        ("CAM 09", "Reolink", "CX410", "192.168.1.109", "External", "LIVE", "H264", 2560, 1440),
        ("CAM 10", "Hikvision", "DS-2CD2047G2", "192.168.1.110", "External", "LIVE", "H265", 2688, 1520),
        ("CAM 11", "Dahua", "IPC-HDW2231T", "192.168.1.111", "External", "OFFLINE", "H264", 1920, 1080),
        ("CAM 12", "Generic ONVIF", "Mini Dome", "192.168.1.112", "Entrance", "NEW", "H264", 1280, 720),
    ]
    geo_fixtures = {
        9: (35.6762, 139.6503, "Japan", "Tokyo", "Mock Fiber Tokyo"),
        10: (25.0330, 121.5654, "Taiwan", "Taipei", "Mock Telecom TW"),
        11: (22.3193, 114.1694, "Hong Kong", "Kowloon", "Mock Net HK"),
    }
    created = 0
    for index, (name, vendor, model, ip, area, status, codec, width, height) in enumerate(fixtures, 1):
        identity = f"mock:{index:02d}"
        camera = db.scalar(select(Camera).where(Camera.identity_key == identity))
        if not camera:
            connection_type = "internet" if area == "External" else "lan"
            camera = Camera(identity_key=identity, name=name, ip=ip, mac=f"02:00:00:00:00:{index:02X}",
                            manufacturer=vendor, model=model, status=status, area_id=areas[area].id,
                            connection_type=connection_type, host=ip, resolved_ip=ip,
                            ptz_support=index in (3, 7), audio_support=index % 3 == 0, is_mock=True,
                            last_seen=datetime.now(timezone.utc) if status == "LIVE" else None)
            db.add(camera)
            db.flush()
            camera.streams.extend([
                CameraStream(kind="main", codec=codec, width=width, height=height, fps=25, validated=status == "LIVE"),
                CameraStream(kind="sub", codec="H264", width=640, height=360, fps=15, validated=status == "LIVE"),
            ])
            created += 1
        enriched = spec_enricher.enrich(vendor, model)
        specs = dict(camera.model_specs or {})
        specs.setdefault("tags", enriched.get("tags") or [])
        camera.model_specs = specs
        if index in geo_fixtures:
            latitude, longitude, country, city, isp = geo_fixtures[index]
            camera.latitude, camera.longitude = latitude, longitude
            camera.country, camera.city, camera.isp = country, city, isp
    db.commit()
    return {"created": created, "total": db.scalar(select(Camera).where(Camera.is_mock.is_(True)).count()) if False else 12}
