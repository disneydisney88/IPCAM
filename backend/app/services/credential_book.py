"""Persistent credential book for the automation pipeline.

The book maps camera IP/host to RTSP credentials and is applied
automatically whenever a matching camera appears (LAN scan discovery or
manual creation), so "scan -> live" needs no manual step. Passwords are
stored only as DPAPI credential-store references; the database keeps
targets and usernames, never secrets.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Camera, CameraStream, Setting
from app.services.credentials import credential_store

BOOK_KEY = "credential_book"
SPLIT_RE = re.compile(r"[;,\t]")


def load_book(db: Session) -> list[dict[str, Any]]:
    setting = db.get(Setting, BOOK_KEY)
    entries = (setting.value.get("entries") if setting and setting.value else None) or []
    return [entry for entry in entries if entry.get("target") and entry.get("credential_ref")]


def save_book(db: Session, entries: list[dict[str, Any]]) -> None:
    setting = db.get(Setting, BOOK_KEY)
    value = {"entries": entries}
    if setting:
        setting.value = value
    else:
        db.add(Setting(key=BOOK_KEY, value=value))


def parse_book_rows(content: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Parse CSV/TXT rows into book entries (password kept for immediate use)."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, line in enumerate(line.strip() for line in content.splitlines() if line.strip()):
        row_number = index + 1
        cells = [cell.strip() for cell in SPLIT_RE.split(line)]
        if row_number == 1 and len(cells) >= 3 and "user" in cells[1].lower():
            continue
        if len(cells) < 3:
            errors.append({"row": row_number, "error": "Need at least ip, username, password"})
            continue
        rows.append({
            "target": cells[0],
            "username": cells[1],
            "password": cells[2],
            "rtsp_path": cells[3] if len(cells) >= 4 and cells[3] else "/",
            "stream_kind": cells[4] if len(cells) >= 5 and cells[4] in ("main", "sub") else "sub",
        })
    return rows, errors


def import_book(db: Session, content: str, replace: bool = True) -> dict[str, Any]:
    """Replace/extend the book from CSV text and return entry summaries."""
    rows, errors = parse_book_rows(content)
    existing = [] if replace else load_book(db)
    existing_targets = {entry["target"].lower() for entry in existing}
    entries = list(existing)
    added = 0
    for row in rows:
        if row["target"].lower() in existing_targets:
            errors.append({"row": 0, "error": f"Duplicate target {row['target']} skipped"})
            continue
        existing_targets.add(row["target"].lower())
        entries.append({
            "target": row["target"],
            "username": row["username"],
            "credential_ref": credential_store.put(f"book-{row['target']}", row["username"], row["password"]),
            "rtsp_path": row["rtsp_path"],
            "stream_kind": row["stream_kind"],
        })
        added += 1
    save_book(db, entries)
    return {"added": added, "total": len(entries), "errors": errors}


def clear_book(db: Session) -> int:
    entries = load_book(db)
    for entry in entries:
        credential_store.delete(entry["credential_ref"])
    save_book(db, [])
    return len(entries)


def apply_entry(db: Session, camera: Camera, entry: dict[str, Any]) -> bool:
    """Write one book entry onto a camera's stream credentials."""
    kind = entry.get("stream_kind") or "sub"
    stored = credential_store.get(entry["credential_ref"])
    if not stored:
        return False
    reference = credential_store.put(f"camera-{camera.id}-{kind}", entry["username"], stored[1])
    stream = db.scalar(select(CameraStream).where(CameraStream.camera_id == camera.id, CameraStream.kind == kind))
    old_reference = stream.rtsp_uri_secret_ref if stream else None
    if not stream:
        stream = CameraStream(camera_id=camera.id, kind=kind)
        db.add(stream)
    stream.rtsp_uri_secret_ref = reference
    specs = dict(camera.model_specs or {})
    specs[f"rtsp_path_{kind}"] = entry.get("rtsp_path") or "/"
    camera.model_specs = specs
    if old_reference and old_reference != reference:
        credential_store.delete(old_reference)
    return True


def apply_book_for_camera(db: Session, camera: Camera) -> int:
    """Auto-apply every book entry whose target matches this camera."""
    targets = {str(camera.ip).lower(), str(camera.host or "").lower(), str(camera.resolved_ip or "").lower()} - {""}
    applied = 0
    for entry in load_book(db):
        if entry["target"].lower() in targets:
            if apply_entry(db, camera, entry):
                applied += 1
    return applied


def apply_book_all(db: Session) -> dict[str, Any]:
    """Apply the whole book to all matching cameras; returns a summary."""
    matched = 0
    cameras_list: list[str] = []
    for camera in db.scalars(select(Camera)).all():
        if apply_book_for_camera(db, camera):
            matched += 1
            cameras_list.append(camera.name)
    return {"matched": matched, "cameras": cameras_list[:20]}


def book_summary(db: Session) -> dict[str, Any]:
    entries = []
    cameras_by_target: dict[str, int] = {}
    for camera in db.scalars(select(Camera)).all():
        for target in {str(camera.ip).lower(), str(camera.host or "").lower()} - {""}:
            cameras_by_target[target] = camera.id
    for entry in load_book(db):
        entries.append({
            "target": entry["target"],
            "username": entry["username"],
            "rtsp_path": entry.get("rtsp_path") or "/",
            "stream_kind": entry.get("stream_kind") or "sub",
            "camera_id": cameras_by_target.get(entry["target"].lower()),
        })
    return {"entries": entries, "total": len(entries)}
