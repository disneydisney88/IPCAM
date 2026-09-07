"""GeoIP location resolution for IP camera targets.

Private, loopback, link-local, multicast and reserved addresses never leave
the machine: they resolve to a "LAN Subnet" label without any HTTP call.
Public addresses are resolved through ip-api.com's free endpoint (HTTP only,
45 req/min) with a 24h in-memory TTL cache and a conservative rate limit so
bulk telemetry refreshes cannot exhaust the quota.

The public interface is async and provider-agnostic; a local MaxMind
GeoLite2 mmdb reader can replace `_fetch` later without touching callers.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GEOIP_API_URL = "http://ip-api.com/json/{ip}"
GEOIP_FIELDS = "status,message,country,city,lat,lon,isp,query"
CACHE_TTL_SECONDS = 24 * 3600
RATE_LIMIT_CALLS = 40
RATE_LIMIT_WINDOW_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 3.0

LOCAL_RESULT: dict[str, Any] = {
    "is_private": True,
    "country": "Local",
    "city": "LAN Subnet",
    "latitude": None,
    "longitude": None,
    "isp": "Local Network",
}

_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
_call_times: list[float] = []


def _reset_state() -> None:
    """Test helper: clear the lookup cache and rate-limit window."""
    _cache.clear()
    _call_times.clear()


def _prune_cache(now: float) -> None:
    expired = [key for key, (stamp, _) in _cache.items() if now - stamp > CACHE_TTL_SECONDS]
    for key in expired:
        _cache.pop(key, None)


def _rate_limited(now: float) -> bool:
    while _call_times and now - _call_times[0] > RATE_LIMIT_WINDOW_SECONDS:
        _call_times.pop(0)
    return len(_call_times) >= RATE_LIMIT_CALLS


def _is_unroutable(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def _fetch(ip: str) -> dict[str, Any] | None:
    """Query the upstream GeoIP provider; kept separate so tests can patch it."""
    url = GEOIP_API_URL.format(ip=ip)
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params={"fields": GEOIP_FIELDS})
    except httpx.HTTPError as exc:
        logger.warning("GeoIP request failed for %s: %s", ip, exc)
        return None
    if response.status_code != 200:
        logger.warning("GeoIP provider returned %s for %s", response.status_code, ip)
        return None
    try:
        data = response.json()
    except ValueError:
        logger.warning("GeoIP provider returned non-JSON payload for %s", ip)
        return None
    if data.get("status") != "success":
        logger.info("GeoIP lookup rejected %s: %s", ip, data.get("message"))
        return None
    return {
        "is_private": False,
        "country": data.get("country"),
        "city": data.get("city"),
        "latitude": data.get("lat"),
        "longitude": data.get("lon"),
        "isp": data.get("isp"),
    }


async def resolve_ip_location(ip_or_host: str) -> dict[str, Any] | None:
    """Resolve a public IP (or hostname) to geographic metadata.

    Returns the LAN placeholder for private addresses, ``None`` when the
    lookup fails or the quota is exhausted. Results are cached for 24h.
    """
    value = (ip_or_host or "").strip()
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        try:
            resolved = await asyncio.get_running_loop().getaddrinfo(value, None, family=socket.AF_INET)
            lookup = resolved[0][4][0]
        except (OSError, IndexError):
            return None
        if _is_unroutable(ipaddress.ip_address(lookup)):
            return dict(LOCAL_RESULT)
    else:
        if _is_unroutable(address):
            return dict(LOCAL_RESULT)
        lookup = value

    now = time.monotonic()
    _prune_cache(now)
    cached = _cache.get(lookup)
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return dict(cached[1]) if cached[1] else None
    if _rate_limited(now):
        logger.warning("GeoIP rate limit reached; skipping lookup for %s", lookup)
        return None
    _call_times.append(now)
    result = await _fetch(lookup)
    _cache[lookup] = (now, result)
    return dict(result) if result else None
