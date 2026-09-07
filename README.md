# IPCAM Scanner + Multi-Camera Dashboard

Windows 11 本機 IPCAM inventory、RFC1918 網路 discovery 與 multi-camera monitoring MVP。程式碼可放在 Google Drive；SQLite、logs、cache 與 snapshots 預設寫到 `%LOCALAPPDATA%\IPCAM`。

## 已完成的 Milestone 1

- FastAPI + SQLite/SQLAlchemy backend，具版本標記及 idempotent baseline migration；包含 Camera、Area、Group、Favorite、Saved View、Scan Session 與 Stream schema。
- React 19 + TypeScript + Vite dashboard，支援 1/4/9/16 camera grid、拖放、縮放、搜尋與 viewport pause。
- `?mock=true` 建立 12 部可持久化的 mock cameras，包含 LIVE、OFFLINE、AUTH REQUIRED、STREAM ERROR、NEW。
- Windows active NIC/subnet detection、RFC1918-only CIDR validation、短 timeout/有限 concurrency TCP discovery。
- ONVIF WS-Discovery multicast 與 response parser；ffprobe metadata parser；go2rtc manager/health/config skeleton。
- Area CRUD、Favorite 即時 SQLite 保存、Saved View 保存 camera order/layout/filter/stream preference。
- PowerShell setup/start/stop/test scripts。已 build 的前端由 FastAPI 同源提供，因此日常啟動不要求 Node 常駐。

## 近期更新

- Dashboard Grid 已加入穩定 container width 測量、layout 鎖定模式與 telemetry 解耦，減少 camera status refresh 造成的重排。
- 新增 external target repository 與單一授權目標掃描入口，並在 Scan Panel 提供 local subnet / external target 雙模式。
- Camera 資料補上 `connection_type`、`host`、`resolved_ip`、`snapshot_url`、`model_specs` 與 `sort_order`，方便後續做 Internet Cameras 分區與規格標籤。

## 第一次設定

在 PowerShell：

```powershell
cd "G:\我的雲端硬碟\IPCAM"
.\scripts\setup.ps1
```

`setup.ps1` 會優先尋找 python.org/winget 安裝的標準 Python 3.12+，不使用 Microsoft Store alias，避免 MSIX 把 `%LOCALAPPDATA%` runtime files redirect 到 package cache。也可用 `IPCAM_PYTHON` 指定 executable。

如果電腦沒有 Node，而需要重新 build 前端：

```powershell
.\scripts\setup.ps1 -InstallNode
```

重新 build 已隨專案提供的前端時使用 `-RebuildFrontend`；一般第一次 setup 會直接使用已驗證的 `frontend\dist`，避免在 Google Drive 建立大量 `node_modules` 小檔案。
`scripts\build-frontend.ps1` 會在本機 temp 目錄安裝/build，然後只把 `dist` 與 lockfile 回寫 Google Drive 專案。

若要從官方 `AlexxIT/go2rtc` GitHub release 下載 Windows x64 binary：

```powershell
.\scripts\setup.ps1 -DownloadGo2rtc
```

go2rtc 缺席時 Dashboard 仍可正常操作 inventory、mock cameras、Area、Favorite 與 Saved Views，video tile 會顯示 `STREAM GATEWAY NOT AVAILABLE`。

## Live View、Credentials 與 Authorized Public Scan

- Camera credentials 由 Windows current-user DPAPI 加密；Dashboard/API 不會回傳 plaintext password 或 secret RTSP URI。
- Settings 可新增、rotation 或刪除 credentials；rotation 會在新 reference 成功保存後清理舊 encrypted blob。
- go2rtc 離線或 crash 時 health check 會嘗試 recovery；無 gateway、未設定 credentials 或 stream unavailable 時 UI 顯示 fallback。
- Authorized Public Scan 預設停用，只接受 enabled allowlist IP/CIDR；最大 `/24`、256 targets，禁止 `0.0.0.0/0`。
- 首次使用 Authorized Public Scan 前，必須由使用者自行設定至少 12 字元的 Admin Password；系統不提供或硬編碼預設密碼，資料庫只保存 scrypt hash。
- Shodan connector 是 optional，API key 以 DPAPI 保存，只 enrichment allowlist 內目標；沒有 key 時其他功能不受影響。

## 啟動

```powershell
cd "G:\我的雲端硬碟\IPCAM"
.\scripts\start-local.ps1
```

正式本機入口：<http://127.0.0.1:8080>

### Streamlit 主入口

`streamlit_app.py` 是可選的 Streamlit 主介面；FastAPI 仍負責掃描、憑證、SQLite 與 go2rtc。先啟動 backend，再執行：

```powershell
cd "G:\我的雲端硬碟\IPCAM"
.\scripts\start-streamlit.ps1
```

Streamlit 入口預設為 <http://127.0.0.1:8501>，可用 `$env:IPCAM_API_BASE_URL` 指向其他受信任的本機 FastAPI 位址。

Mock Mode：

```powershell
.\scripts\start-local.ps1 -Mock
```

或開啟 <http://127.0.0.1:8080/?mock=true>。

停止：

```powershell
.\scripts\stop-local.ps1
```

## 測試

```powershell
.\scripts\test-system.ps1
```

測試涵蓋 schema migration、favorite/area/saved-view persistence、private CIDR validation、camera identity、mock scan progress、ONVIF parser、ffprobe parser 與 go2rtc missing-binary health state。

## Runtime data

預設：

```text
%LOCALAPPDATA%\IPCAM\
├─ data\ipcam.db
├─ logs\
├─ cache\
└─ snapshots\
```

可在啟動前改用：

```powershell
$env:IPCAM_DATA_DIR = "D:\IPCAM-Runtime"
.\scripts\start-local.ps1
```

`data-backup\` 只供手動 backup/export，不作 active database。

Python venv 放在 `%USERPROFILE%\.ipcam\venv`，避免 Google Drive 寫入及 Microsoft Store Python 對 `%LOCALAPPDATA%` 的 App Package redirect。

## 安全範圍

Scanner 只接受完整位於 `10.0.0.0/8`、`172.16.0.0/12` 或 `192.168.0.0/16` 的 IPv4 CIDR，單次最多 4096 hosts。沒有 internet-wide scanning、default-password guessing、credential stuffing、authentication bypass 或 exploit modules。只可用於自己擁有或獲授權管理的網路。

## 尚未完成

Milestone 1 保留但尚未深入實作的部分：authenticated ONVIF DeviceInformation/Capabilities/Media Profiles、vendor-specific RTSP path discovery、Windows Credential Manager/DPAPI 真正寫入、go2rtc dynamic hot reload/auto-restart、real camera WebRTC player wiring、mDNS/ARP/OUI enrichment、per-camera realtime online/offline watcher、snapshot capture 與 audio controls。詳見 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
