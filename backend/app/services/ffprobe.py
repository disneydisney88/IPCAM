from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, asdict
from fractions import Fraction
from typing import Any

from app.config import settings


def parse_ffprobe(payload: dict[str, Any], latency_ms: float | None = None) -> dict[str, Any]:
    video = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in payload.get("streams", []) if s.get("codec_type") == "audio"), {})
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    try:
        fps = round(float(Fraction(rate)), 2)
    except (ValueError, ZeroDivisionError):
        fps = None
    bit_rate = video.get("bit_rate") or payload.get("format", {}).get("bit_rate")
    return {
        "codec": (video.get("codec_name") or "").upper() or None,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
        "bitrate": int(bit_rate) if bit_rate and str(bit_rate).isdigit() else None,
        "audio_codec": (audio.get("codec_name") or "").upper() or None,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        "validated": bool(video),
    }


def probe_stream(uri: str, timeout: int = 8) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        settings.ffprobe_path, "-v", "error", "-rtsp_transport", "tcp", "-show_streams",
        "-show_format", "-of", "json", uri,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        return {"validated": False, "error": "ffprobe is not installed"}
    except subprocess.TimeoutExpired:
        return {"validated": False, "error": "ffprobe timed out"}
    latency = (time.perf_counter() - started) * 1000
    if result.returncode != 0:
        # Deliberately do not return stderr because it can echo credential-bearing URIs.
        return {"validated": False, "error": "Stream validation failed"}
    return parse_ffprobe(json.loads(result.stdout), latency)

