from __future__ import annotations

import asyncio
import ipaddress
from typing import Any

from app.scanners.external import scan_external_target


class PublicScanCoordinator:
    def __init__(self) -> None:
        self.running = False
        self.cancelled = False
        self.status: dict[str, Any] = {"state": "disabled", "checked": 0, "total": 0, "succeeded": 0, "failed": 0}

    @staticmethod
    def expand(value: str) -> list[str]:
        try: network = ipaddress.ip_network(value, strict=False)
        except ValueError: return [value]
        if network.is_private or network.is_loopback or network.prefixlen < 24:
            raise ValueError("Authorized public CIDR must be public and /24 or smaller")
        hosts = [str(ip) for ip in network.hosts()]
        if len(hosts) > 256: raise ValueError("Public scan is limited to 256 targets")
        return hosts

    async def run(self, targets: list[str], rate_limit: float, concurrency: int, timeout: float) -> dict[str, Any]:
        if self.running: raise ValueError("Public scan already running")
        self.running, self.cancelled = True, False
        self.status = {"state": "running", "checked": 0, "total": len(targets), "succeeded": 0, "failed": 0}
        semaphore = asyncio.Semaphore(concurrency)
        async def one(host: str):
            if self.cancelled: return
            async with semaphore:
                if self.cancelled: return
                try:
                    await asyncio.wait_for(scan_external_target(host), timeout=timeout)
                    self.status["succeeded"] += 1
                except Exception:
                    self.status["failed"] += 1
                self.status["checked"] += 1
                await asyncio.sleep(1 / rate_limit)
        try: await asyncio.gather(*(one(host) for host in targets))
        finally:
            self.running = False
            self.status["state"] = "cancelled" if self.cancelled else "completed"
        return self.status

    def stop(self):
        self.cancelled = True
        self.status["state"] = "stopping" if self.running else self.status["state"]


public_scanner = PublicScanCoordinator()
