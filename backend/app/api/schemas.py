from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AreaInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CameraInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    ip: str
    mac: str | None = None
    onvif_uuid: str | None = None
    serial: str | None = None
    manufacturer: str = "Generic ONVIF"
    model: str = "Unknown"
    firmware: str | None = None
    area_id: int | None = None
    connection_type: Literal["lan", "internet"] = "lan"
    host: str | None = None
    resolved_ip: str | None = None
    snapshot_url: str | None = None
    model_specs: dict[str, Any] | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    country: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    isp: str | None = Field(default=None, max_length=200)
    sort_order: int = 0


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    area_id: int | None = None
    status: str | None = None
    connection_type: Literal["lan", "internet"] | None = None
    host: str | None = None
    resolved_ip: str | None = None
    snapshot_url: str | None = None
    model_specs: dict[str, Any] | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    country: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    isp: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None


class FavoriteInput(BaseModel):
    favorite: bool


class GroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupMembersInput(BaseModel):
    camera_ids: list[int]


class SavedViewItemInput(BaseModel):
    camera_id: int
    position: int
    layout: dict[str, Any] = Field(default_factory=dict)


class SavedViewInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grid_size: Literal[1, 4, 9, 16] = 4
    filters: dict[str, Any] = Field(default_factory=dict)
    stream_preference: Literal["main", "sub"] = "sub"
    items: list[SavedViewItemInput] = Field(default_factory=list)


class ScanInput(BaseModel):
    cidr: str
    mock: bool = False


class ExternalTargetInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port_overrides: str | None = None
    notes: str | None = None
    enabled: bool = True


class ExternalScanInput(BaseModel):
    target_id: str | None = None
    name: str | None = None
    host: str | None = None
    port_overrides: str | None = None
    notes: str | None = None
    mode: Literal["quick", "deep"] = "quick"


class AllowlistImportInput(BaseModel):
    format: Literal["csv", "json"]
    content: str = Field(min_length=1, max_length=1_000_000)


class SchedulerUpdateInput(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=60, ge=5, le=10_080)
    scan_mode: Literal["quick", "deep"] = "quick"
    target_timeout_seconds: int = Field(default=15, ge=2, le=300)


class CameraCredentialInput(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)
    rtsp_path: str = Field(default="/", min_length=1, max_length=500)
    stream_kind: Literal["main", "sub"] = "sub"


class AdminPasswordInput(BaseModel):
    password: str = Field(min_length=12, max_length=500)


class PublicScanInput(BaseModel):
    target_id: str
    rate_limit: float = Field(default=2, gt=0, le=20)
    concurrency: int = Field(default=4, ge=1, le=20)
    timeout_seconds: float = Field(default=10, ge=2, le=60)


class ShodanKeyInput(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)
