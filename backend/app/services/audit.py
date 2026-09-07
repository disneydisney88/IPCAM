from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(db: Session, action: str, status: str = "success", *, target_id: str | None = None,
                 target_name: str | None = None, details: dict[str, Any] | None = None) -> AuditLog:
    db.execute(delete(AuditLog).where(AuditLog.created_at < datetime.now(timezone.utc) - timedelta(days=90)))
    entry = AuditLog(action=action, status=status, target_id=target_id, target_name=target_name,
                     details=details or {})
    db.add(entry)
    return entry
