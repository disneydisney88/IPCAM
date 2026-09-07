from __future__ import annotations

import asyncio
import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select

from app.database.core import session_scope
from app.models import Camera, ScanSession
from app.scanners.onvif import ws_discover
from app.services.identity import camera_identity
from app.services.network import validate_private_cidr


CAMERA_PORTS = (80, 443, 554, 8000, 8080, 8554, 8899)


class ScanCoordinator:
    def __init__(self) -> None:
        self.events: dict[int, list[dict[str, object]]] = {}
        self.done: set[int] = set()

    def create(self, cidr: str) -> int:
        network = validate_private_cidr(cidr)
        with session_scope() as db:
            session = ScanSession(cidr=str(network), total=max(network.num_addresses - 2, 0))
            db.add(session)
            db.flush()
            scan_id = session.id
        self.events[scan_id] = []
        return scan_id

    def emit(self, scan_id: int, event: str, **data: object) -> None:
        self.events.setdefault(scan_id, []).append({"event": event, "data": data})

    async def _open_ports(self, ip: str, timeout: float = 0.22) -> list[int]:
        async def check(port: int) -> int | None:
            try:
                _reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
                writer.close()
                await writer.wait_closed()
                return port
            except (OSError, asyncio.TimeoutError):
                return None

        return [port for port in await asyncio.gather(*(check(port) for port in CAMERA_PORTS)) if port]

    async def run(self, scan_id: int, mock: bool = False) -> None:
        with session_scope() as db:
            session = db.get(ScanSession, scan_id)
            if not session:
                return
            session.status = "RUNNING"
            cidr = session.cidr
            total = session.total
        self.emit(scan_id, "progress", status="RUNNING", checked=0, total=total, candidates=0, onvif=0, streams=0)
        if mock:
            await self._run_mock(scan_id, total)
            return

        network = validate_private_cidr(cidr)
        onvif_devices = await ws_discover(timeout=2.0)
        onvif_ips: set[str] = set()
        for device in onvif_devices:
            xaddrs = device.get("xaddrs") or []
            for url in xaddrs if isinstance(xaddrs, list) else []:
                ip = urlsplit(str(url)).hostname
                if ip and ipaddress.ip_address(ip) in network:
                    onvif_ips.add(ip)
                    self._upsert_candidate(ip, [80], str(device.get("uuid") or "") or None, str(url))
                    self.emit(scan_id, "camera_found", ip=ip, onvif=True)

        semaphore = asyncio.Semaphore(64)
        checked = 0
        candidates = len(onvif_ips)

        async def inspect(ip: str) -> tuple[str, list[int]]:
            async with semaphore:
                return ip, await self._open_ports(ip)

        tasks = [asyncio.create_task(inspect(str(host))) for host in network.hosts()]
        try:
            for task in asyncio.as_completed(tasks):
                ip, ports = await task
                checked += 1
                if ports and ip not in onvif_ips:
                    candidates += 1
                    self._upsert_candidate(ip, ports)
                    self.emit(scan_id, "camera_found", ip=ip, ports=ports, onvif=False)
                if checked == total or checked % max(1, min(16, total // 20 or 1)) == 0:
                    self._update(scan_id, checked, candidates, len(onvif_ips), 0)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
        self._complete(scan_id, checked, candidates, len(onvif_ips), 0)

    async def _run_mock(self, scan_id: int, total: int) -> None:
        checked = 0
        for checked in range(0, total + 1, max(1, total // 16 or 1)):
            candidates = min(5, checked // max(1, total // 5 or 1))
            onvif = min(3, checked // max(1, total // 3 or 1))
            streams = min(5, checked // max(1, total // 5 or 1))
            self._update(scan_id, min(checked, total), candidates, onvif, streams)
            await asyncio.sleep(0.08)
        self._complete(scan_id, total, 5, 3, 5)

    def _upsert_candidate(self, ip: str, ports: list[int], onvif_uuid: str | None = None, onvif_url: str | None = None) -> None:
        identity = camera_identity(onvif_uuid=onvif_uuid, ip=ip)
        with session_scope() as db:
            camera = db.scalar(select(Camera).where(Camera.identity_key == identity))
            if not camera:
                camera = Camera(identity_key=identity, name=f"New camera {ip}", ip=ip, status="NEW")
                db.add(camera)
            camera.onvif_uuid = onvif_uuid or camera.onvif_uuid
            camera.onvif_url = onvif_url or camera.onvif_url
            camera.http_port = next((p for p in ports if p in (80, 443, 8080)), None)
            camera.rtsp_port = next((p for p in ports if p in (554, 8554)), None)
            camera.last_seen = datetime.now(timezone.utc)

    def _update(self, scan_id: int, checked: int, candidates: int, onvif: int, streams: int) -> None:
        with session_scope() as db:
            session = db.get(ScanSession, scan_id)
            if session:
                session.checked = checked
                session.candidates = candidates
                session.onvif_count = onvif
                session.streams_found = streams
                total = session.total
            else:
                total = 0
        self.emit(scan_id, "progress", status="RUNNING", checked=checked, total=total,
                  candidates=candidates, onvif=onvif, streams=streams)

    def _complete(self, scan_id: int, checked: int, candidates: int, onvif: int, streams: int) -> None:
        with session_scope() as db:
            session = db.get(ScanSession, scan_id)
            if session:
                session.status = "COMPLETED"
                session.checked = checked
                session.candidates = candidates
                session.onvif_count = onvif
                session.streams_found = streams
                session.completed_at = datetime.now(timezone.utc)
                total = session.total
            else:
                total = 0
        self.emit(scan_id, "complete", status="COMPLETED", checked=checked, total=total,
                  candidates=candidates, onvif=onvif, streams=streams)
        self.done.add(scan_id)


coordinator = ScanCoordinator()

