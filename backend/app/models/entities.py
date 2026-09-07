from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.core import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Area(Base):
    __tablename__ = "areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    cameras: Mapped[list["Camera"]] = relationship(back_populates="area")


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    ip: Mapped[str] = mapped_column(String(45), index=True)
    mac: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onvif_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    serial: Mapped[str | None] = mapped_column(String(120), nullable=True)
    oui_vendor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(120), default="Generic ONVIF")
    model: Mapped[str] = mapped_column(String(160), default="Unknown")
    firmware: Mapped[str | None] = mapped_column(String(120), nullable=True)
    onvif_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rtsp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connection_type: Mapped[str] = mapped_column(String(16), default="lan")
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    snapshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_specs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    isp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    ptz_support: Mapped[bool] = mapped_column(Boolean, default=False)
    audio_support: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id", ondelete="SET NULL"), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_stream: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    area: Mapped[Area | None] = relationship(back_populates="cameras")
    streams: Mapped[list["CameraStream"]] = relationship(back_populates="camera", cascade="all, delete-orphan")
    favorite: Mapped["Favorite | None"] = relationship(back_populates="camera", cascade="all, delete-orphan", uselist=False)
    group_memberships: Mapped[list["CameraGroupMember"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class ExternalTarget(Base):
    __tablename__ = "external_targets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255))
    port_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    target_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    targets_count: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    cancelled: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class CameraStream(Base):
    __tablename__ = "camera_streams"
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="sub")
    rtsp_uri_secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    camera: Mapped[Camera] = relationship(back_populates="streams")


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    camera: Mapped[Camera] = relationship(back_populates="favorite")


class CameraGroup(Base):
    __tablename__ = "camera_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    members: Mapped[list["CameraGroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class CameraGroupMember(Base):
    __tablename__ = "camera_group_members"
    __table_args__ = (UniqueConstraint("group_id", "camera_id", name="uq_group_camera"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("camera_groups.id", ondelete="CASCADE"))
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    group: Mapped[CameraGroup] = relationship(back_populates="members")
    camera: Mapped[Camera] = relationship(back_populates="group_memberships")


class SavedView(Base):
    __tablename__ = "saved_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    grid_size: Mapped[int] = mapped_column(Integer, default=4)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stream_preference: Mapped[str] = mapped_column(String(20), default="sub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    items: Mapped[list["SavedViewItem"]] = relationship(back_populates="view", cascade="all, delete-orphan", order_by="SavedViewItem.position")


class SavedViewItem(Base):
    __tablename__ = "saved_view_items"
    __table_args__ = (UniqueConstraint("view_id", "camera_id", name="uq_view_camera"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    view_id: Mapped[int] = mapped_column(ForeignKey("saved_views.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    layout: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    view: Mapped[SavedView] = relationship(back_populates="items")
    camera: Mapped[Camera] = relationship()


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    cidr: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    checked: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    onvif_count: Mapped[int] = mapped_column(Integer, default=0)
    streams_found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
