# Architecture

## Runtime topology

```text
Chrome / Edge :8080
        │ HTTP + SSE
        ▼
FastAPI / Uvicorn :8080 ── SQLite ── %LOCALAPPDATA%\IPCAM\data\ipcam.db
        │
        ├── RFC1918 LAN scanner ── TCP / WS-Discovery ── authorized LAN cameras
        ├── ffprobe subprocess ── validated RTSP metadata
        └── go2rtc API :1984 ── WebRTC :8555 (optional in Milestone 1)
```

The Vite production bundle is served by FastAPI to keep normal startup to one local process plus optional go2rtc. During frontend development, Vite uses port 8080 and proxies `/api` to a backend on port 8000.

## Boundaries

- `app/api`: validation and HTTP/SSE contracts.
- `app/database`: SQLite engine/session ownership. WAL mode and foreign keys are enabled.
- `app/models`: persistent domain schema. Camera identity is separate from mutable IP.
- `app/scanners`: two-phase discovery boundary. Milestone 1 implements WS-Discovery plus light, limited TCP checks.
- `app/services`: NIC/CIDR rules, camera identity, ffprobe parsing, credential abstraction.
- `app/media`: go2rtc executable/config/process/health boundary.
- `frontend/src/components`: memoized camera tiles, grid, scan, wizard, navigation and settings.

## Discovery safety

`validate_private_cidr` rejects public, IPv6 and over-large networks. A scan uses the seven camera-relevant ports with a 220 ms connection timeout and a 64-host semaphore. WS-Discovery is multicast to `239.255.255.250:3702`. No credentials are guessed.

## Stream policy

- Grid and saved views default to sub streams.
- Fullscreen reserves main-stream preference.
- `IntersectionObserver` pauses tiles outside the viewport.
- Browser APIs never receive RTSP secret URIs. `CameraStream` stores an opaque secret reference rather than the credential-bearing URI.
- When go2rtc is unavailable, inventory and persistence keep working.

## Next milestones

1. Authenticated ONVIF DeviceInformation/GetCapabilities/GetProfiles/GetStreamUri with safe secret lookup.
2. ARP, mDNS and maintained OUI enrichment; deduplication across changed IPs.
3. ffprobe execution pipeline and persisted stream profiles.
4. go2rtc registration/reload/restart plus per-camera WebRTC player URL.
5. Per-camera status topics, snapshot worker, real offline watcher and richer wizard preview.

