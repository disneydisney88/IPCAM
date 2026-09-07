from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import ValidationError

from app.api.schemas import ExternalTargetInput
from app.scanners.external import validate_authorized_target


ALLOWED_FIELDS = {"name", "host", "port_overrides", "notes", "enabled"}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "true").strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError("enabled must be true or false")


def parse_allowlist(content: str, format_name: str) -> tuple[list[ExternalTargetInput], list[dict[str, Any]]]:
    if format_name == "json":
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc.msg}") from exc
        rows = raw.get("targets") if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise ValueError("JSON must be an array or an object containing a targets array")
    elif format_name == "csv":
        rows = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
        if not rows:
            raise ValueError("CSV contains no target rows")
    else:
        raise ValueError("Unsupported allowlist format")

    valid: list[ExternalTargetInput] = []
    errors: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows, 1):
        try:
            if not isinstance(raw_row, dict):
                raise ValueError("row must be an object")
            row = {key: value for key, value in raw_row.items() if key in ALLOWED_FIELDS}
            row["enabled"] = _as_bool(row.get("enabled", True))
            payload = ExternalTargetInput.model_validate(row)
            if payload.port_overrides:
                ports = [part.strip() for part in payload.port_overrides.split(",") if part.strip()]
                if not ports or any(not part.isdigit() or not 1 <= int(part) <= 65535 for part in ports):
                    raise ValueError("port_overrides must contain comma-separated ports between 1 and 65535")
            validate_authorized_target(payload.host)
            valid.append(payload)
        except (ValueError, ValidationError) as exc:
            errors.append({"row": index, "error": str(exc)})
    return valid, errors
