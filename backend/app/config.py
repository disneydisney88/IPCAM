from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    db_path: Path
    logs_dir: Path
    cache_dir: Path
    snapshots_dir: Path
    go2rtc_path: Path
    ffprobe_path: str
    go2rtc_api: str


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    data_dir = Path(os.environ.get("IPCAM_DATA_DIR", local_app_data / "IPCAM")).expanduser().resolve()
    logs_dir = data_dir / "logs"
    cache_dir = data_dir / "cache"
    snapshots_dir = data_dir / "snapshots"
    for directory in (data_dir, logs_dir, cache_dir, snapshots_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        db_path=data_dir / "data" / "ipcam.db",
        logs_dir=logs_dir,
        cache_dir=cache_dir,
        snapshots_dir=snapshots_dir,
        go2rtc_path=project_root / "tools" / "go2rtc" / "go2rtc.exe",
        ffprobe_path=os.environ.get("IPCAM_FFPROBE", "ffprobe"),
        go2rtc_api=os.environ.get("IPCAM_GO2RTC_API", "http://127.0.0.1:1984"),
    )


settings = load_settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)

