# IPCAM Monitor — Codex Handover

## 2026-09-07 v0.4.0 Streamlit 主入口與 GitHub 快照

- 新增根目錄 `streamlit_app.py`，作為可選的 Streamlit 主介面；FastAPI 仍是掃描、SQLite、credentials、go2rtc 的唯一資料服務層。
- 新增 `scripts/start-streamlit.ps1`，預設在 `http://127.0.0.1:8501` 啟動 Streamlit，並以 `IPCAM_API_BASE_URL` 連接本機 FastAPI。
- Streamlit 分成 Dashboard、External Scan、Authorized Public Scan 三個 tab；External Scan 只呼叫既有單一目標 API，不新增公網任意搜尋。
- `backend/requirements.txt` 已加入 `streamlit>=1.40,<2`。
- 已完成 GitHub `main` 推送：commit `764366d`（之後的 Streamlit 變更待本次提交）。
- 本次驗證：backend `34 passed`、frontend production build 成功、`streamlit_app.py` Python syntax compile 成功。

## 2026-08-24 v0.3.1 安全與可靠性更新

- 已移除預設 Admin Password；首次使用須自行設定至少 12 字元密碼。舊版帶有 `must_change` 的預設雜湊會被視為未設定，不能用來解鎖。
- Admin Unlock 採 scrypt、5 次失敗暫鎖 5 分鐘、15 分鐘 session timeout；改密碼會撤銷所有既有解鎖 token。
- go2rtc 已加入背景 health monitoring、連續故障偵測、自動 restart/recovery、指數 reconnect 間隔，以及 timeout/authentication/unavailable 分類。
- Scheduler run 具 queued/running/completed/failed/cancelled 狀態、每 target timeout、執行中取消及同 target concurrent scan 防護。
- Audit Log 保持 pagination、action/status/date filters、action autocomplete 與分批 streaming CSV export。
- Shodan 無 API key 時回報 `not_configured` 並保持停用；只可 enrichment 已啟用 allowlist target。
- Dashboard 的相機總數、Online、Offline、Last Scan、Scheduler、近期發現、近期離線、近期 jobs、Public Scan 與 go2rtc 均由 backend summary 提供。
- 自動化驗證：backend 34 tests passed、Python compile、TypeScript/production build、npm audit 0 vulnerabilities。

本文件供下一個 Codex 接手。專案根目錄：`G:\我的雲端硬碟\IPCAM`。

## 目前結論

- 本機 Dashboard 已可由 FastAPI 提供，網址為 `http://127.0.0.1:8080/`。
- External IP 模式已支援單一授權目標、已儲存目標、最近一次目標一鍵重掃。
- External scan 只做 DNS、TCP port 探測、HTTP 基本指紋、品牌初步判斷及 auth challenge 回報。
- 已有受限的 Shodan API key 儲存與 allowlist enrichment；尚未加入任意公網資產搜尋。
- 已完成 CSV/JSON authorized allowlist 匯入、enabled targets 背景排程及 90 天 Audit Log。
- Scheduler 現支援 active target 安全取消與 Running / Stopping / Stopped 狀態；Audit Log 支援分頁、篩選及 CSV 匯出。
- Scheduler 已有持久化 run history 與 per-target timeout；Audit CSV 已改為 bounded-memory streaming。
- go2rtc Live View 已接 Camera/CameraStream，缺少 gateway 或 credentials 時回傳明確 fallback。
- credentials 以 Windows current-user DPAPI 加密到本機資料目錄，SQLite 只保存 opaque `dpapi-*` reference。
- v0.3.0 加入 credential CRUD/rotation cleanup、go2rtc recovery、Authorized Public Scan、optional Shodan enrichment 及 Dashboard summary。
- Public Scan 預設 Disabled；首次使用必須自行設定至少 12 字元的 Admin Password，僅保存 scrypt hash，沒有預設密碼。

## Path Map

### Backend

- `backend/app/main.py`：FastAPI app、CORS、API router、前端 `dist` 靜態掛載。
- `backend/app/api/routes.py`：REST API 路由；包含 cameras、areas、views、local scan、external targets。
- `backend/app/api/schemas.py`：Pydantic request schema；包含 `ExternalTargetInput`、`ExternalScanInput`。
- `backend/app/scanners/engine.py`：區網 CIDR scan coordinator 與 SSE progress。
- `backend/app/scanners/onvif.py`：ONVIF/WS-Discovery 探測。
- `backend/app/scanners/external.py`：單一外部目標驗證、DNS、TCP ports、HTTP fingerprint、brand matching。
- `backend/app/database/core.py`：SQLite engine/session。
- `backend/app/database/migrations.py`：SQLite schema migration；包含 `external_targets`。
- `backend/app/models/entities.py`：SQLAlchemy models；包含 `ExternalTarget` 與 Camera metadata。
- `backend/app/media/go2rtc_manager.py`：go2rtc health/process abstraction；目前若沒有 binary，Dashboard 仍可運行。
- `backend/app/services/ffprobe.py`：stream metadata probe。
- `backend/app/services/credentials.py`：憑證抽象層預留；尚未接 Windows DPAPI。
- `backend/app/services/allowlist.py`：CSV/JSON allowlist 解析、欄位與授權目標驗證。
- `backend/app/services/scheduler.py`：只掃描 enabled allowlist targets 的持久化背景排程。
- `backend/app/services/audit.py`：稽核事件寫入與 90 天 retention。
- `backend/app/services/credentials.py`：Windows DPAPI credential blob store；secret 不進 SQLite、API 或 audit。

### Frontend

- `frontend/src/App.tsx`：全域 dashboard state、sections、layout edit mode。
- `frontend/src/components/ScanPanel.tsx`：Local Subnet / External IP mode、快速授權目標、最近目標、terminal progress。
- `frontend/src/components/CameraGrid.tsx`：穩定 grid layout；狀態更新不應重算座標。
- `frontend/src/components/CameraCard.tsx`：snapshot/live placeholder、status、connection type、spec tags。
- `frontend/src/lib/api.ts`：frontend API client；external scan 使用 `POST /api/external-targets/scan`。
- `frontend/src/types.ts`：Camera、ExternalTarget、ExternalScanResult、ScanProgress types。
- `frontend/src/styles.css`：dashboard、scan modal、external quick action styles。
- `frontend/src/hooks/useStableContainerWidth.ts`：ResizeObserver debounce/jitter guard。

### Operations / Docs

- `scripts/setup.ps1`：建立 Python environment、安裝相依套件。
- `scripts/start-local.ps1`：啟動 FastAPI/本機 Dashboard；不會自動 reload backend code。
- `scripts/stop-local.ps1`：停止本機服務。
- `scripts/build-frontend.ps1`：在暫存目錄安裝 Node dependencies 並把 build 複製到 `frontend/dist`。
- `scripts/test-system.ps1`：系統測試入口。
- `docs/API.md`：API 說明。
- `docs/ARCHITECTURE.md`：系統分層與約束。
- `README.md`：使用與開發說明。
- `CHANGELOG.md`：版本變更記錄。
- `streamlit_app.py`：Streamlit 主介面；只作 API client，不直接讀 SQLite 或 credentials。
- `scripts/start-streamlit.ps1`：Streamlit 啟動器；可用 `-ApiBaseUrl`、`-Port` 覆寫預設值。
- `docs/DEPLOYMENT_SECRETS.md`：GitHub、Streamlit secrets、Admin password 與 Shodan key 的安全部署規則。

## 已完成

- External target CRUD：`GET/POST /api/external-targets`。
- External scan：`POST /api/external-targets/scan`，支援 `target_id` 或單一 `host`。
- Authorized target enabled/disabled 檢查。
- Hostname、IP、optional port 格式驗證。
- private/loopback/link-local/multicast 預設阻擋。
- 文件示例網段 `192.0.2.0/24`、`198.51.100.0/24`、`203.0.113.0/24` 允許作為測試輸入。
- Quick/deep port set。
- HTTP Server/title/WWW-Authenticate 基本指紋。
- Hikvision、Dahua、Axis、Uniview、Xiongmai、Reolink、Vivotek 初步 brand rules。
- Scan result 的 `open_ports` 已回傳實際 port numbers。
- frontend build 已可成功完成。
- Allowlist import API：`POST /api/external-targets/import`，支援 CSV/JSON、逐列錯誤及 host-based update。
- Scheduler API：`GET/PUT /api/scheduler`、`POST /api/scheduler/run`。
- Scheduler Stop API：`POST /api/scheduler/stop`；取消中的 target 記錄為 `cancelled`，不更新成功掃描時間。
- Audit Log API：`GET /api/audit-logs` 支援 page/page_size、date_from/date_to、action、status；事件保留 90 天。
- Audit CSV：`GET /api/audit-logs/export.csv`，沿用相同篩選並輸出 UTF-8 BOM CSV。
- Scheduler history：`GET /api/scheduler/runs`；設定包含 `target_timeout_seconds`（2–300 秒）。
- Audit actions：`GET /api/audit-logs/actions`，供 UI autocomplete 使用。
- Camera credentials：`PUT /api/cameras/{id}/credentials`；只回傳 configured 狀態。
- Live View：`GET /api/cameras/{id}/live?kind=sub`；只回傳 go2rtc player URL 或安全 fallback 狀態。
- Credential CRUD：`GET/PUT/DELETE /api/cameras/{id}/credentials`；password 永不回傳，rotation 後清理舊 blob。
- Admin：`GET /api/admin/status`、`POST /api/admin/unlock`；5 次失敗暫鎖 5 分鐘。
- Public Scan：`GET/PUT /api/public-scan`、`POST /preview|start|stop`；只接受 enabled allowlist target ID。
- Shodan：`GET /api/shodan/status`、`PUT /api/shodan/key`、`GET /api/shodan/enrich/{target_id}`；只 enrichment allowlist，不擴大 scope。
- Dashboard：`GET /api/dashboard/summary`。
- Settings UI 已整合 allowlist 匯入、scheduler 狀態/停止控制、audit 篩選/分頁/CSV 下載。

## 尚未完成

- Streamlit 尚未取代 React 的全部互動功能；目前是可運行的主介面骨架，Live video、layout editor、完整設定 CRUD 仍以 React dashboard 為準。
- Streamlit 套件需先由 `scripts/setup.ps1` 安裝 requirements；未安裝時不能執行 `python -m streamlit`。

- Shodan 目前只有 `GET /api/shodan/status`、`PUT /api/shodan/key`、`GET /api/shodan/enrich/{target_id}`；沒有 `/api/shodan/search`。
- 沒有 Shodan dork / `product:` / `has_screenshot:` 公網搜尋。
- 沒有全球 IP space 掃描、Mass-CIDR、第三方 IP camera discovery。
- 沒有 Shodan screenshot 下載、RTSP 第一幀擷取或匿名串流預覽。
- 沒有密碼猜測、credential stuffing、弱密碼爆破或 exploit。
- 沒有自動新增陌生設備到 cameras；目前需要使用者確認/授權。
- 沒有整個 Dashboard 的登入頁；目前 Admin password 只保護 Public Scan、Shodan key 與相關管理操作。
- 沒有 Windows DPAPI credential vault 完整實作。
- go2rtc binary 不一定存在；沒有 binary 時 live stream 不可用，但 inventory/mock UI 可用。

## Password / Shodan / 自動化邊界

### Admin password

- UI 位於 Settings → `Authorized Public Scan`。
- 首次設定要求最少 12 個字元；密碼以 scrypt hash 儲存，不會回傳明文。
- 解鎖 token 的有效期是 15 分鐘；連續失敗會暫時 lockout。
- Camera credentials 是另一層功能，使用 Windows DPAPI adapter；它不是 Dashboard login。

Shodan 只能採用「使用者證明擁有或獲授權的 scope」模式：

1. API key 由使用者在本機設定，不進 git、不進前端、不進 log。
2. 只接受 allowlist 的單一 IP、hostname 或使用者明確擁有的 CIDR。
3. 禁止任意 `tag:camera`、地域篩選、全網產品搜尋及陌生第三方資產匯入。
4. Shodan 結果先進入待確認清單，不直接加入 cameras 或拉取影像。
5. 所有自動化工作要有 rate limit、audit log、停止按鈕與結果保留期限。

可安全實作的替代方案：匯入使用者自己的 CSV/JSON allowlist，定時只掃清單內的目標，並在 UI 顯示最後掃描時間與差異。

## 驗證方式

```powershell
# Build frontend
$env:Path = 'C:\Users\klcho\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;C:\Users\klcho\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback;' + $env:Path
& 'G:\我的雲端硬碟\IPCAM\scripts\build-frontend.ps1'

# Restart local service after backend changes
& 'G:\我的雲端硬碟\IPCAM\scripts\stop-local.ps1'
& 'G:\我的雲端硬碟\IPCAM\scripts\start-local.ps1' -NoBrowser

# Health / external target API
Invoke-WebRequest 'http://127.0.0.1:8080/api/health'
Invoke-WebRequest 'http://127.0.0.1:8080/api/external-targets'

# Start Streamlit client after FastAPI is running
& 'G:\我的雲端硬碟\IPCAM\scripts\start-streamlit.ps1'
# Optional custom backend / port
& 'G:\我的雲端硬碟\IPCAM\scripts\start-streamlit.ps1' -ApiBaseUrl 'http://127.0.0.1:8080' -Port 8501
```

注意：`start-local.ps1` 啟動的是沒有 reload 的 uvicorn process。修改 backend 後必須重啟，否則會看到舊 route 的 `404` 或 `405`。

## 給下一個 Codex 的交接清單

### 已完成

1. **來源與入口**：唯一工作目錄是 `G:\我的雲端硬碟\IPCAM`；Git remote 是 `https://github.com/disneydisney88/IPCAM.git`，分支 `main`。
2. **後端**：FastAPI 由 `backend/app/main.py` 啟動，預設 `127.0.0.1:8080`；修改 backend 後要停止/重啟，不會 hot reload。
3. **Streamlit**：使用 `streamlit_app.py` 作 client 入口；它不應直接存取 SQLite、明文 credentials 或掃描未授權目標。
4. **密碼**：Admin password 從 Streamlit/React 的 Authorized Public Scan 設定；最少 12 字元，API 只接受短期 unlock token。
5. **外部掃描**：只可呼叫 `POST /api/external-targets/scan` 的單一 host/已啟用 allowlist；禁止 Mass-CIDR、弱密碼猜測、exploit。
6. **Shodan**：目前只有 allowlist enrichment，沒有 `/api/shodan/search`；key 由受保護管理 API 寫入本機 credential store。
7. **Git secrets**：`.env*`、`.streamlit/secrets.toml`、keys/certs/credentials JSON 已加入 `.gitignore`；禁止把真實 key commit。

### 下一步建議

1. 在全新 Windows 環境執行 `scripts/setup.ps1`，確認 Streamlit 安裝後啟動 FastAPI，再啟動 Streamlit。
2. 驗證 `http://127.0.0.1:8501` 三個 tab，尤其是 Admin setup/unlock、External Scan 錯誤訊息與 allowlist 限制。
3. 若要把 React 功能逐項搬到 Streamlit，先補測試與 API client，再逐步遷移，不要讓 Streamlit 直接繞過 FastAPI security boundary。
4. 每次修改後執行 `scripts/test-system.ps1`、frontend build、`python -m py_compile streamlit_app.py`，並更新本文件與 `CHANGELOG.md`。

## 建議下一個 Codex 的順序

1. 若要接入 Shodan，先由使用者明確提供自有 scope 與本機 API key，再評估受限 inventory connector。
2. 在有實際攝影機與 go2rtc binary 的 Windows 主機做端到端 WebRTC/RTSP 驗收。
3. 視需要加入 credential rotation/delete UI；目前 API 可安全覆寫 reference，但不主動刪除舊 DPAPI blob。
4. 視需要加入 scheduler history pagination 與 run detail target breakdown。
