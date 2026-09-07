from __future__ import annotations

import hashlib
import re


def normalize_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac).upper()
    if len(cleaned) != 12:
        return None
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def camera_identity(*, mac: str | None = None, onvif_uuid: str | None = None, serial: str | None = None,
                    manufacturer: str | None = None, model: str | None = None, ip: str | None = None) -> str:
    normalized_mac = normalize_mac(mac)
    if onvif_uuid:
        return f"onvif:{onvif_uuid.strip().lower()}"
    if normalized_mac:
        return f"mac:{normalized_mac}"
    if serial:
        source = f"{manufacturer or ''}|{model or ''}|{serial}".lower()
        return f"serial:{hashlib.sha256(source.encode()).hexdigest()[:24]}"
    if ip:
        return f"ip:{ip.strip().lower()}"
    raise ValueError("At least one stable camera identifier or IP is required")

