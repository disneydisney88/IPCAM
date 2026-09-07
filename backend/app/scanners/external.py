from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.scanners.fingerprints import BrandSignature, FINGERPRINT_DATABASE
from app.scanners.ports_matrix import get_ports_for_mode


DOC_TEST_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


def _parse_target(target: str) -> tuple[str, int | None]:
    parsed = urlsplit(f"//{target}", scheme="http")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("Invalid target")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid target port")
    return host, parsed.port


def validate_authorized_target(target: str) -> tuple[str, int | None]:
    host, port = _parse_target(target.strip())
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,255}", host):
            raise ValueError("Target must be a single hostname or IP address")
    else:
        if (
            (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast)
            and not any(ip in network for network in DOC_TEST_NETWORKS)
        ):
            raise ValueError("Only public targets are allowed for external scans")
    return host, port


def _resolve_ipv4(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


async def _check_port(host: str, port: int, timeout: float) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _probe_http(host: str, port: int, timeout: float) -> dict[str, Any]:
    scheme = "https" if port in {443, 8443} else "http"
    url = f"{scheme}://{host}:{port}/"
    result: dict[str, Any] = {"url": url, "status_code": None, "server": None, "title": None, "realm": None, "auth_required": False}
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            result["status_code"] = response.status_code
            result["server"] = response.headers.get("server")
            if response.status_code == 401:
                result["auth_required"] = True
                result["realm"] = response.headers.get("www-authenticate")
            elif "text/html" in response.headers.get("content-type", ""):
                match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
                if match:
                    result["title"] = re.sub(r"\s+", " ", match.group(1)).strip()
                result["realm"] = response.headers.get("www-authenticate")
    except httpx.HTTPError:
        pass
    return result


def _match_brand(server: str | None, title: str | None, realm: str | None) -> BrandSignature | None:
    haystack = " ".join(part.lower() for part in (server, title, realm) if part)
    for signature in FINGERPRINT_DATABASE.values():
        tokens = [token.lower() for token in
                  signature.server_headers + signature.title_keywords + signature.realm_keywords]
        if any(token and token in haystack for token in tokens):
            return signature
    return None


def _candidate_uris(signature: BrandSignature | None, host: str, port: int | None) -> dict[str, list[str]]:
    if not signature:
        return {"rtsp": [f"rtsp://{host}:{port or 554}/live/ch0"], "snapshot": [f"http://{host}:{port or 80}/snapshot.jpg"]}
    rtsp_port = port or 554
    http_port = port or 80
    return {
        "rtsp": [f"rtsp://{host}:{rtsp_port}{path}" for path in signature.default_rtsp_paths],
        "snapshot": [f"http://{host}:{http_port}{path}" for path in signature.snapshot_endpoints],
    }


async def scan_external_target(target: str, mode: str = "quick", timeout: float = 1.5) -> dict[str, Any]:
    host, explicit_port = validate_authorized_target(target)
    resolved_ip = _resolve_ipv4(host)
    ports = [explicit_port] if explicit_port else list(get_ports_for_mode(mode))

    port_checks = await asyncio.gather(*(_check_port(host, port, timeout) for port in ports))
    open_ports = [port for port, is_open in zip(ports, port_checks) if is_open]

    http_fingerprints = [await _probe_http(host, port, timeout) for port in open_ports if port in {80, 443, 8080, 8443, 8888, 8000, 8001, 8081, 8088, 8090, 9000}]
    signature = None
    for probe in http_fingerprints:
        signature = _match_brand(probe.get("server"), probe.get("title"), probe.get("realm"))
        if signature:
            break

    auth_required = any(probe.get("auth_required") for probe in http_fingerprints)
    candidates = _candidate_uris(signature, host, explicit_port)
    return {
        "target": target,
        "host": host,
        "resolved_ip": resolved_ip,
        "open_ports": open_ports,
        "brand": signature.brand_name if signature else None,
        "auth_required": auth_required,
        "fingerprints": http_fingerprints,
        "candidates": candidates,
    }
