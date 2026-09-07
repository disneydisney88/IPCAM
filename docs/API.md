# API

Interactive OpenAPI is available at `http://127.0.0.1:8080/docs` while the backend is running.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Backend and go2rtc state |
| GET/POST | `/api/cameras` | Camera inventory / manual save |
| PATCH/DELETE | `/api/cameras/{id}` | Update or delete camera |
| PUT | `/api/cameras/{id}/favorite` | Persist favorite state |
| GET/POST | `/api/areas` | List/create physical areas |
| PATCH/DELETE | `/api/areas/{id}` | Rename/delete area |
| GET/POST | `/api/groups` | Logical cross-area groups |
| PUT | `/api/groups/{id}/members` | Replace group membership |
| GET/POST | `/api/views` | Saved layout definitions |
| PUT/DELETE | `/api/views/{id}` | Update/delete a saved view |
| GET | `/api/system/network/interfaces` | Active private IPv4 NICs and suggested CIDRs |
| POST | `/api/scans` | Start an RFC1918 scan |
| GET | `/api/scans/{id}/events` | SSE progress/camera events |
| GET | `/api/media/health` | go2rtc availability |
| POST | `/api/mock/ensure` | Idempotently seed 12 mock cameras |

Camera responses intentionally exclude passwords, RTSP URIs and credential references.

