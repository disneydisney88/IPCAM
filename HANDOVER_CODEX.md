# IPCAM Monitor — Agent 交接手冊（HANDOVER）

> 更新：2026-09-13 · 版本 v0.5.1+ · 主分支 main · 最新 commit 見 `git log`
> 本檔給下一個接手的 AI agent / 開發者。讀完這份 + `CHANGELOG.md` 即可完整接手。
> 專案慣例：全程使用**繁體中文**回覆（見 `AGENTS.md`）。

---

## 0. 60 秒摘要

- **這是什麼**：本機優先（local-first）的 IP 攝影機管理儀表板。FastAPI 是唯一資料服務層（SQLite + DPAPI 憑證 + 掃描引擎 + go2rtc 串流），React 儀表板與 Streamlit 是兩個客戶端介面。
- **唯一工作目錄**：`G:\我的雲端硬碟\IPCAM`（Google Drive 同步資料夾；不要用 OneDrive 的 IPCAM 目錄）
- **Git**：`origin = https://github.com/disneydisney88/IPCAM.git`，branch `main`，commit 後直接 push main（憑證已存 Windows Credential Manager）
- **三條不可違反的紅線**（架構上已排除，見 §4）：
  1. 只掃描**使用者擁有或獲明確授權**的目標（allowlist 綁定）——**禁止隨機/大範圍 IP 掃描**
  2. **禁止密碼猜測/字典攻擊/弱密碼偵測**——憑證只來自使用者自己上傳的清單
  3. **禁止未經使用者確認自動把陌生設備變成正式相機**
- **驗收最低標準**：`backend 53 tests passed` + frontend build OK + `py_compile streamlit_app.py`

---

## 1. 環境與關鍵路徑

| 項目 | 路徑 / 值 | 備註 |
|---|---|---|
| 專案根目錄 | `G:\我的雲端硬碟\IPCAM` | Google Drive 同步 |
| **Python venv** | `C:\Users\klcho\.ipcam\venv\Scripts\python.exe` | **必用此 venv**；系統 Python 缺 sqlalchemy/pytest |
| 執行期資料 | `%LOCALAPPDATA%\IPCAM\` | `data\ipcam.db`(SQLite v5)、`logs\`、`cache\`、`snapshots\`、`credentials\`(DPAPI) |
| 前端產物 | `frontend\dist\` | 由 build 腳本產生並隨 git 提交 |
| Node | 系統 v24（`C:\Program Files\nodejs`） | build 腳本在 temp 目錄自行 npm install |
| ngrok 執行檔 | `%LOCALAPPDATA%\IPCAM\tools\ngrok\ngrok.exe` | v3.39 |
| ngrok 設定 | `%LOCALAPPDATA%\ngrok\ngrok.yml`（authtoken）、`%LOCALAPPDATA%\IPCAM\ngrok-domain.txt`（網域） | **網域：`woof-gathering-devalue.ngrok-free.dev`（永久，勿改）** |
| cloudflared | `tools\cloudflared\cloudflared.exe` | **備用**。勿從 Drive 資料夾直接執行 exe（同步鎖檔會 in-page error crash） |
| Streamlit Cloud | `kuumphnrwsbatuubpxupfv.streamlit.app`（帳號 disneydisney88） | Secret：`IPCAM_API_BASE_URL = "https://woof-gathering-devalue.ngrok-free.dev"` |
| 排程任務 | Windows 工作排程器 **"IPCAM Autostart"** | AtLogOn、隱藏視窗執行 `scripts\autostart.ps1` 看門狗 |
| 看門狗日誌 | `%LOCALAPPDATA%\IPCAM\logs\autostart.log` | 每 60 秒自檢一次 |

### 對外網址
| 用途 | 網址 | 備註 |
|---|---|---|
| 本機 React 儀表板 | `http://127.0.0.1:8080` | 全功能（建議在家用） |
| 本機 Streamlit | `http://127.0.0.1:8501` | 輕量版 + ⚙️ 自動化分頁 |
| **公網永久入口（ngrok）** | `https://woof-gathering-devalue.ngrok-free.dev` | 瀏覽器首次會有 ngrok 提示頁（按 Visit Site）；API 加 `ngrok-skip-browser-warning` header 即免 |
| Streamlit 雲端 | `https://kuumphnrwsbatuubpxupfv.streamlit.app` | 客戶端，需隧道活著才有資料 |

---

## 2. Path Map（檔案級）

### Backend（`backend/app/`）
| 檔案 | 內容 |
|---|---|
| `main.py` | FastAPI 工廠：**Dashboard 鎖 middleware**（所有 `/api/*` 需 `X-Admin-Unlock`；豁免 `/api/health`、`/api/admin/*`、`/api/scans/{id}/events`、`/api/cameras/{id}/snapshot.jpg`；未設密碼→428、無效→401、鎖定→429；env `IPCAM_DASHBOARD_LOCK=0` 可關閉，**tests 已預設關閉**）、CORS、前端 static 掛載 |
| `config.py` | Settings：`data_dir = env IPCAM_DATA_DIR 或 %LOCALAPPDATA%\IPCAM`；db=`data\ipcam.db`；`IPCAM_GO2RTC_API`(預設 127.0.0.1:1984)、snapshots_dir |
| `api/routes.py` | 全部端點（見 §8）。亮點：`create_camera` 自動 enrich tags + 自動套 credential book；`import-credentials`（單次套用）；`credentials/book/*`（持久密碼清單）；`cameras/{id}/snapshot`+`snapshot.jpg`；`telemetry`；`external-targets/scan` 含 GeoIP；`start_scan` 完成後自動抓最多 12 台快照（`run_scan_with_snapshots`） |
| `api/schemas.py` | Pydantic inputs（CameraInput/Update 含經緯度；CredentialImportInput） |
| `database/migrations.py` | **schema v5**：cameras + `latitude/longitude/country/city/isp`；external_targets + geo 四欄。冪等 `_add_column` |
| `models/entities.py` | Camera（geo 欄位、model_specs JSON）、ExternalTarget、CameraStream（憑證參照）、AuditLog、Setting、SchedulerRun、ScanSession、SavedView… |
| `scanners/external.py` | `validate_authorized_target`（僅公網；**私有/保留網段擋下**；`DOC_TEST_NETWORKS` 三段測試網放行）+ `scan_external_target`（DNS、埠矩陣、HTTP 指紋、brand、auth、rtsp/snapshot candidates） |
| `scanners/engine.py` | 區網掃描協調 + SSE。`_upsert_candidate`：發現/更新相機時 **自動套用 credential book**（best-effort try/except） |
| `scanners/ports_matrix.py`、`fingerprints.py` | quick/deep 埠清單；7 品牌指紋（server/title/realm 關鍵字 + RTSP 路徑 + 快照端點） |
| `scanners/onvif.py` | WS-Discovery |
| `media/go2rtc_manager.py` | go2rtc 行程、config 寫入（api 127.0.0.1:1984、webrtc 127.0.0.1:8555）、`register_stream`、`player_url`（`IPCAM_GO2RTC_MODE` env：`webrtc`（預設）或 `hls`——**遠端觀看用 hls**） |
| `services/geoip.py` | `resolve_ip_location`：私有/保留→LAN Subnet **絕不對外查詢**；公網走 ip-api.com（HTTP、45/min）；24h 快取 + 負快取 + 40/min 限速；`_fetch` 是唯一替換點（可換 GeoLite2 mmdb） |
| `services/snapshots.py` | `capture`：品牌快照端點優先→generic fallback；digest→basic auth；存 `snapshots_dir`；回 `snapshot_url`（API 相對路徑） |
| `services/credential_book.py` | **持久密碼清單**：parse（逗號/分號/TAB、標題列自動略過）、import（DPAPI refs；replace/append）、`apply_book_for_camera`（**engine 與 create_camera 都會呼叫 = 自動套用**）、apply_all、book_summary |
| `services/specs.py` | spec_enricher：`config/camera-specs.json`（3 個型號）→ tags（如 4MP/ColorVu/PoE） |
| `services/admin_auth.py` | scrypt(N=16384) 密碼、token 15 分鐘、5 次失敗鎖 5 分鐘；存 `settings.admin_auth` |
| `services/credentials.py` | Windows **DPAPI** store（`put/get/delete`）；DB/回應永不含明文 |
| `services/scheduler.py` | 只掃 enabled allowlist 目標；queued/running/stopping/stopped；run 歷史 |
| `services/public_scan.py` | 需 Admin 啟用；/24 上限 256 目標 |
| `services/audit.py` | 90 天保留 |
| `services/network.py` | RFC1918 驗證、網卡偵測（`_default_gateway` 用 **System32 route.exe 絕對路徑** + None guard——曾在此 crash 導致儀表板空白） |
| `tests/` | **53 項**：lock、geoip、credential book、telemetry、snapshot、scheduler、network…；`conftest.py` 設 `IPCAM_DATA_DIR`(temp) 與 `IPCAM_DASHBOARD_LOCK=0` |

### Frontend（`frontend/src/`，React 19 + Vite 7 + Leaflet 5）
| 檔案 | 內容 |
|---|---|
| `lib/api.ts` | fetch wrapper：自動帶 `X-Admin-Unlock`（sessionStorage `ipcam.unlockToken`）+ `bypass-tunnel-reminder`/`ngrok-skip-browser-warning`；401/428/429 → `lockHandler`（非 /api/admin/ 路徑） |
| `App.tsx` | 鎖定流程（status→setup/locked/open；`unlockDashboard`；🔒 按鈕）、telemetry 30 秒輪詢、`loadData`（interfaces 失敗不拖垮相機載入）、grid 1/4/6/9/12/16、Live Wall toggle、Map section、fullscreen（go2rtc iframe） |
| `components/LockScreen.tsx` | setup/locked 兩模式鎖屏 |
| `components/CameraMapView.tsx` | react-leaflet + OSM；marker 顏色隨 telemetry；popup 含快照/ISP/開直播；側欄列 LAN 無座標相機 |
| `components/LiveWall.tsx` | 多格 WebRTC 牆（每格 = go2rtc `stream.html` iframe；fetch cameraLive per camera） |
| `components/CameraCard.tsx` | 📍 地點徽章、telemetry 狀態燈/FPS、Snapshot 按鈕（呼叫 API）、Info 浮層（含 Update GeoIP） |
| `components/ScanPanel.tsx` | Local/External 掃描、終端步驟、GeoIP 顯示、授權目標一鍵掃 |
| `components/CameraGrid.tsx` | react-grid-layout（可拖曳/持久化）；buildLayout 支援 6/12 |
| `Sidebar.tsx` | 導覽（含 Map View） |
| `hooks/useStableContainerWidth.ts`、`useVisibility.ts` | 防抖寬度、可視性（省資源） |
| `styles.css` | 全部樣式（含 lock/map/live-wall/info overlay） |

### Streamlit（`streamlit_app.py`）
- `api_call`：自帶 unlock token + 隧道 bypass headers；401/428/429 → 設 `lock_required`
- 側欄「Backend URL 臨時覆寫」（session 覆寫隧道網址，免改 Secrets）
- 鎖定 gate（首次可在雲端直接建立 Admin 密碼）、Lock now 按鈕
- Tabs：**Dashboard**（指標、相機卡含 📍/快照縮圖、▶ 即時影像 iframe、st.map、🔑 密碼 TXT 匯入）、**External Scan**（含 GeoIP 顯示）、**Authorized Public Scan**、**⚙️ 自動化**（密碼清單 book 上傳/套用/清空、IP allowlist 上傳、排程控制、結果說明）

### Scripts（`scripts/`）
| 腳本 | 用途 |
|---|---|
| `setup.ps1` | 首次安裝（venv `%USERPROFILE%\.ipcam\venv` + requirements） |
| `start-local.ps1` / `stop-local.ps1` | 啟/停 backend(+go2rtc)；`-NoBrowser`、`-Mock` |
| `start-streamlit.ps1` | 啟 Streamlit（env `IPCAM_PYTHON` 可指定 venv） |
| `build-frontend.ps1` | temp 目錄 npm install + tsc/vite build → 複製回 `frontend\dist` |
| `test-system.ps1` | pytest + 前端建置 |
| `start-ngrok.ps1` | **永久隧道**：`-Authtoken -Domain`（一次性設定）；會自動起後端 |
| `autostart.ps1` | 看門狗（排程任務呼叫）：自動起後端 + 守 ngrok domain |
| `start-tunnel-free.ps1` | localtunnel 固定子域（備用；免費服務不穩） |
| `start-tunnel.ps1` | trycloudflare 快速隧道（備用；URL 每次變） |

### 設定與文件
| 檔案 | 內容 |
|---|---|
| `requirements.txt`（根目錄） | **Streamlit Cloud 用**（streamlit + httpx）——雲端只會讀根目錄這份 |
| `backend/requirements.txt` | 後端完整相依 |
| `config/camera-specs.json`、`camera-oui.json` | 規格 enrichment 資料 |
| `docs/API.md`、`docs/ARCHITECTURE.md`、`docs/DEPLOYMENT_SECRETS.md` | 既有文件 |
| `docs/IPCAM_Monitor_使用說明書_v0.5.1.docx` | 給終端使用者的中文說明書（Word） |
| `CHANGELOG.md`、`HANDOVER_CODEX.md`（本檔） | 變更紀錄與交接 |

---

## 3. 核心資料流

**區網掃描**：`POST /api/scans` → coordinator（TCP 埠探測 + ONVIF）→ `_upsert_candidate` 建立相機（狀態 NEW）→ **自動套 credential book** → 完成後自動抓快照（≤12 台）→ 前端 SSE 顯示進度。

**外部掃描**：`POST /api/external-targets/scan` → `validate_authorized_target`（僅公網/allowlist）→ 埠探測 → HTTP 指紋（品牌/auth）→ `resolve_ip_location`（GeoIP）→ 回應含 `location`；有 target_id 時座標存進 external_targets → 稽核。

**Live View**：`GET /api/cameras/{id}/live` → 讀 DPAPI 憑證 → 組 RTSP URI → go2rtc `register_stream` → 回 `player_url`（`IPCAM_GO2RTC_API/stream.html?src=...&mode=IPCAM_GO2RTC_MODE`）。前端 fullscreen/Live Wall 用 iframe 播放。**預設 mode=webrtc 且 API=127.0.0.1:1984 → 只有本機可播**；要遠端播放：為 1984 開隧道 + 設 `IPCAM_GO2RTC_API=<隧道>` 與 `IPCAM_GO2RTC_MODE=hls` 重啟後端。

**自動化流水線（⚙️ 自動化分頁）**：上傳**密碼清單**（DPAPI 持久化）+ **IP 清單**（allowlist）→ 啟用排程 → 排程掃描/手動掃描發現配對 IP 的相機時**自動套憑證** → Streamlit ▶ / React Live Wall 立即可播。

**遠端存取**：`scripts\autostart.ps1`（排程任務 AtLogOn）保證後端 + ngrok 隧道活著 → Streamlit Cloud（Secret 已設永久網址）與任何瀏覽器開 `https://woof-gathering-devalue.ngrok-free.dev` 都能連回（鎖屏保護）。

---

## 4. 安全模型與紅線

- **Dashboard 鎖**：無密碼時整個 API 回 428（僅 health/admin 豁免）；token 15 分鐘；5 次失敗鎖 5 分鐘。豁免清單與原因見 `main.py` 註解（EventSource/`<img>` 無法帶 header）。
- **密碼**：scrypt 雜湊存 `settings.admin_auth`。**重置方法**：停服務 → `DELETE FROM settings WHERE key='admin_auth'` → 重啟即回首次設定畫面（同時使所有 token 失效）。
- **憑證**：相機 RTSP 帳密、Shodan key、credential book 全走 DPAPI（目前使用者層級）；DB 只存 `dpapi-*` 參照；API/日誌永不回明文。
- **紅線（對使用者已多次聲明，勿協助繞過）**：不做隨機/地理範圍 IP 大量掃描、不做密碼猜測或「偵測可用密碼」、不導入陌生第三方設備。市面上「黑瞳」類 App 的流程屬未經授權入侵（港《刑事罪行條例》161 條、陸《刑法》285 條等），本專案架構刻意排除。系統性的合法對應 = allowlist + scheduler + credential book + Live Wall（均已實作）。

---

## 5. 日常 SOP 與鐵律

```powershell
# 啟動（本機全套）
scripts\start-local.ps1 -NoBrowser      # backend + go2rtc (8080)
scripts\start-streamlit.ps1             # streamlit (8501)

# 停止
scripts\stop-local.ps1

# 修改後端後必須重啟（無熱重載）
scripts\stop-local.ps1; scripts\start-local.ps1 -NoBrowser

# 驗證
cd backend; & $env:USERPROFILE\.ipcam\venv\Scripts\python.exe -m pytest tests -q   # 預期 53 passed
powershell -File scripts\build-frontend.ps1                                        # 前端
& <venv>\python.exe -m py_compile streamlit_app.py
Invoke-WebRequest http://127.0.0.1:8080/api/health
```

**鐵律 / 陷阱（血淚清單）**：
1. **重啟前先 stop，並確認只剩一組 uvicorn**（`Get-CimInstance Win32_Process | ? CommandLine -like '*uvicorn*'`）。重複 start 會多行程競爭同一埠 → 資料忽有忽無。venv 的 python.exe 會 spawn 子進程，**同一實例 = 2 個 python.exe（父子）屬正常**。
2. pytest 必須 `cd backend` 用 venv python；系統 Python 缺件。
3. `route print` 在部分 PATH 會解析失敗 → network.py 已用 System32 絕對路徑修復，勿回退。
4. **不要把 exe 放在 Drive 同步資料夾直接執行**（cloudflared 曾 in-page error crash）；工具一律放 `%LOCALAPPDATA%\IPCAM\tools\`。
5. localtunnel 免費服務不穩（2026-09-11 全域掛過）；對外隧道首選 **ngrok**，trycloudflare 為備用。
6. 本機 DNS 是 114.114.114.114，**解析不到 trycloudflare 新網址**（本機瀏覽器測試需改用 1.1.1.1 或 `--resolve`）；Streamlit Cloud（海外）不受影響。
7. Python 3.13 的 `ipaddress.is_private` 視 TEST-NET（203.0.113.x 等）為 private → geoip 標 LAN 不對外查；external.py 的 `DOC_TEST_NETWORKS` 是刻意放行掃描，兩者不衝突。
8. 修改後端不重啟 → 新端點 404/舊行為。
9. `CAM 01–12` 與 3 台 "New camera" 是 **mock/示範資料**（`is_mock=True`），不會有真實串流；`?mock=true` 才會觸發 ensure。
10. Streamlit Cloud 只讀**根目錄** `requirements.txt`（已放 streamlit+httpx）；後端相依在 `backend/requirements.txt`。
11. ngrok 免費版：瀏覽器有提示頁（API 無感）；authtoken 在 `%LOCALAPPDATA%\ngrok\ngrok.yml`，**勿提交 git**。

---

## 8. API 速覽（全部需 `X-Admin-Unlock`，標 ✅ 者豁免）

| 端點 | 說明 |
|---|---|
| ✅ `GET /api/health` | 健康與 go2rtc 狀態 |
| ✅ `POST /api/admin/setup` `/unlock`、`GET /api/admin/status` | 密碼建立/解鎖/狀態 |
| `GET /api/cameras`、`POST /api/cameras`、`PATCH/DELETE /api/cameras/{id}` | 相機 CRUD（建立自動 enrich + 套 book） |
| `POST /api/cameras/{id}/snapshot`、`GET .../snapshot.jpg`（✅GET） | 抓圖/取圖 |
| `POST /api/cameras/{id}/geoip`、`/enrich-specs` | 手動刷新地理/規格 |
| `PUT/GET/DELETE /api/cameras/{id}/credentials` | 憑證（DPAPI） |
| `POST /api/cameras/import-credentials` | 批次憑證套用（即時，內容為 CSV/TXT 文字） |
| `GET /api/credentials/book`、`POST .../import?replace=`、`POST .../apply`、`DELETE .../book` | 持久密碼清單 |
| `GET /api/telemetry?ids=` | TCP 健康探測（≤64） |
| `POST /api/external-targets[/scan|/import]`、GET/DELETE | allowlist 與掃描（回應含 location） |
| `GET/PUT /api/scheduler`、`POST /run` `/stop`、`GET /runs` | 排程 |
| `POST /api/scans`、`GET /api/scans/{id}/events`(✅) | 區網掃描 + SSE |
| `GET /api/audit-logs`、`/export.csv`、`/actions` | 稽核 |
| `GET/PUT /api/public-scan`、`/preview|/start|/stop`、Shodan `/status`、`/key`、`/enrich/{id}` | Admin 進階 |

---

## 9. 未完成 / 下一步建議

1. **遠端 Live Wall**：`IPCAM_GO2RTC_API` + `IPCAM_GO2RTC_MODE=hls` 已支援，但隧道(1984)與後端重啟仍是手動；可把它納入 `autostart.ps1` 全自動。
2. **GeoIP 離線化**：接 MaxMind GeoLite2（只需替換 `geoip.py::_fetch`），避開 ip-api 的 HTTP 明文與限速。
3. **真實相機上線**：目前 DB 內是 mock 資料；接真機後可刪 mock。
4. **ngrok 瀏覽器提示頁**：可用付費版或教使用者在瀏覽器加 `ngrok-skip-browser-warning` header。
5. Streamlit 雲端 UI 仍為輕量客戶端；完整功能以 React 為準（刻意設計，勿繞過 API 直接讀 SQLite）。
6. `HANDOVER_CODEX.md` 的 v0.3.1–v0.5.1 逐項歷史已壓縮至 `CHANGELOG.md`，需要細節再查 git log。

---

## 10. 版本歷史摘要（細節見 CHANGELOG.md）

| 版本 | 日期 | 重點 |
|---|---|---|
| v0.3.1 | 08-24 | 移除預設密碼、go2rtc 監控、排程生命週期、Audit |
| v0.4.0 | 09-07 | Streamlit 主入口、GitHub 快照 |
| v0.5.0 | 09-07 | GeoIP 地圖（Leaflet）、快照服務、telemetry、spec enrichment、憑證批次匯入 |
| v0.5.1 | 09-07 | **全 Dashboard 密碼鎖**、network.py 修復、Live Wall、6/12 宮格、後端 URL 覆寫 |
| v0.5.2 | 09-08~12 | credential book 自動套用、⚙️ 自動化分頁、ngrok 永久隧道 + 看門狗、Streamlit 雲端部署修復 |

> 接手後若做了修改：更新 `CHANGELOG.md` + 本檔對應段落 + `git push origin main`（使用者會由 Streamlit Cloud 自動同步）。
