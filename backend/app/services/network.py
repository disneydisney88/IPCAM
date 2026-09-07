from __future__ import annotations

import ipaddress
import socket
import subprocess
from dataclasses import dataclass, asdict
from typing import Any

import psutil


PRIVATE_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
))


def validate_private_cidr(cidr: str, max_hosts: int = 4096) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise ValueError("Invalid CIDR") from exc
    if network.version != 4 or not any(network.subnet_of(private) for private in PRIVATE_NETWORKS):
        raise ValueError("Only RFC1918 private IPv4 networks are allowed")
    if network.num_addresses - 2 > max_hosts:
        raise ValueError(f"Network is too large for one scan (maximum {max_hosts} hosts)")
    return network


def _default_gateway() -> str | None:
    try:
        result = subprocess.run(
            ["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[0] == "0.0.0.0" and fields[1] == "0.0.0.0":
                return fields[2]
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def detect_interfaces() -> list[dict[str, Any]]:
    gateway = _default_gateway()
    stats = psutil.net_if_stats()
    interfaces: list[dict[str, Any]] = []
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET or address.address.startswith("127.") or not address.netmask:
                continue
            try:
                network = ipaddress.ip_network(f"{address.address}/{address.netmask}", strict=False)
            except ValueError:
                continue
            if not any(network.subnet_of(private) for private in PRIVATE_NETWORKS):
                continue
            interfaces.append({
                "name": name,
                "ip": address.address,
                "netmask": address.netmask,
                "subnet": str(network),
                "gateway": gateway if gateway and ipaddress.ip_address(gateway) in network else None,
                "suggested_cidr": str(network),
            })
    return interfaces

