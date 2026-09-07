# Changelog

## 0.3.1 - 2026-08-24

### Added

- Added first-use Admin Password setup and an authenticated Change Password UI; password rotation revokes existing unlock sessions.
- Added Admin session expiry metadata, rolling failed-login throttling, temporary lockout state, and dedicated authentication tests.
- Added continuous go2rtc health monitoring, crash detection, bounded automatic restart, reconnect backoff, timeout/authentication error classification, and recovery mock tests.
- Added Scheduler queued/running/completed/failed/cancelled lifecycle handling and duplicate concurrent target protection.
- Connected Last Scan, recent discoveries, recent offline cameras, and recent scan jobs to the dashboard summary.

### Security

- Removed the hard-coded default Admin Password and precomputed default hash. New installations require the user to choose a password of at least 12 characters.
- Admin secrets remain absent from API responses, frontend source, URLs, logs, and audit details.
- Shodan now explicitly reports `not_configured` and remains disabled without an API key.

## 0.3.0 - 2026-08-24

### Added

- Added go2rtc health recovery/restart handling and multi-camera dashboard Live View entry points with snapshot/status fallback.
- Added masked credential CRUD UI, DPAPI rotation cleanup, and credential status/delete APIs.
- Added a default-disabled Authorized Public Scan with scrypt Admin Unlock, failed-login lockout, allowlist enforcement, /24 and 256-target caps, preview, rate/concurrency/timeout controls, cancellation, and secret-free audit events.
- Added optional DPAPI-secured Shodan enrichment restricted to enabled allowlist targets; IPCAM remains functional without a key.
- Added homepage summary cards for cameras, scheduler, Public Scan, and go2rtc health.
- Added security regression tests for unlock enforcement, Internet-wide range rejection, throttling, credential rotation cleanup, and optional Shodan operation.

### Security

- Admin Password is stored only as a scrypt hash; no plaintext secret is stored.
- Public Scan rejects unrestricted CIDRs and cannot run without both admin unlock and an enabled allowlist entry.
- Camera passwords and Shodan keys never appear in frontend responses, URLs, logs, or audit details.

## 0.2.0 - 2026-08-24

### Added

- Added persistent Scheduler run history with timing, target totals, succeeded, failed, cancelled, and duration metrics.
- Added configurable per-target timeout protection so an unresponsive target cannot block the scheduler.
- Added recent run history to Settings and an Audit action autocomplete selector.
- Added bounded-memory Audit CSV streaming in batches while preserving all existing filters.
- Added go2rtc Live View registration for existing Camera/CameraStream records, with clear gateway/credential/snapshot fallbacks.
- Added a current-user Windows DPAPI credential vault; SQLite stores opaque references only.
- Added credential and live-view APIs that never return passwords, usernames, secret references, or credential-bearing RTSP URIs.

### Changed

- Advanced SQLite schema to version 4 using an additive `scheduler_runs` migration; no existing rows are modified or removed.
- Expanded regression coverage for history, timeout, streaming export, action discovery, DPAPI round trips, and Live View fallback.

## 0.1.3 - 2026-08-24

### Added

- Added safe cancellation for an active scheduled external-target scan with Running, Stopping, and Stopped states.
- Added `POST /api/scheduler/stop`; cancelled targets are audited and never receive a successful `last_scan` update.
- Added Audit Log pagination plus date, action, and status filters.
- Added filtered UTF-8 CSV export through `GET /api/audit-logs/export.csv`.
- Added Settings UI controls for stopping scans, viewing scheduler state, filtering/paging audit events, and downloading CSV.

### Changed

- Disabling the scheduler prevents subsequent scheduled targets and future rounds from starting while allowing the active target to end consistently.
- Expanded backend coverage to include cancellation consistency, disabled scheduling, pagination, filtering, and CSV export.

## 0.1.2 - 2026-08-24

### Added

- Added CSV/JSON authorized allowlist import with per-row validation, host-based updates, and rejected-row reporting.
- Added a persistent external-target scheduler with enable/disable, quick/deep mode, interval configuration, and run-now control.
- Added a 90-day audit log for allowlist changes, manual/scheduled scans, failures, and scheduler configuration.
- Added Settings UI controls for allowlist import, scheduler management, and recent audit events.

### Changed

- Advanced the SQLite schema to version 3 with the `audit_logs` table and indexes.
- Kept all automated scans restricted to enabled allowlist targets.
- Moved backend test temporary data under the project test directory for reliable execution from the Google Drive path.

## 0.1.1 - 2026-08-20

### Changed

- Hardened the camera dashboard grid so layout state no longer reacts to runtime telemetry refreshes.
- Added stable container width measurement with jitter filtering and delayed layout mounting.
- Added external target repository and a single-target external scan endpoint for authorized hosts/IPs.
- Extended camera records with connection metadata, host resolution, snapshot URL, model specs, and sort order.
- Added an external target scan mode to the Scan panel and an Internet Cameras section in the sidebar.

## 0.1.0 - 2026-08-16

### Added

- Initial Windows-local FastAPI/SQLite and React 19/Vite monorepo.
- Persistent cameras, areas, groups, favorites, streams, scans and saved layouts.
- 12-camera Mock Mode and 1/4/9/16 draggable/resizable dashboard.
- Active NIC detection, RFC1918 validation, light private subnet scan and ONVIF WS-Discovery parser.
- ffprobe metadata parser and optional go2rtc manager/health/config skeleton.
- PowerShell setup, start, stop and system-test entry points.

### Deferred

- Authenticated ONVIF media profile probing and vendor-specific stream discovery.
- Production credential adapter and live WebRTC registration/player wiring.
# 0.4.0 - 2026-09-07

- 新增 `streamlit_app.py` 主介面與 `scripts/start-streamlit.ps1`。
- Streamlit 提供 Dashboard、單一授權 External Scan、Authorized Public Scan 操作頁。
- 新增 Streamlit dependency；secrets 仍只允許本機/部署平台 secret store。
