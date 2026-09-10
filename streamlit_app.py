"""Streamlit entry point for the IPCAM dashboard.

The FastAPI service remains the source of truth for scanning, credentials and
SQLite persistence.  This file is a thin local-first UI client; it never
stores camera passwords or API keys in Streamlit session state.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st
import streamlit.components.v1 as components


API_BASE_DEFAULT = os.getenv("IPCAM_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
API_BASE = API_BASE_DEFAULT


def set_api_base(url: str) -> None:
    """Override the backend base for this session (e.g. a new tunnel URL)."""
    global API_BASE
    API_BASE = (url or API_BASE_DEFAULT).rstrip("/")


def api_call(method: str, path: str, **kwargs: Any) -> Any:
    """Call the local FastAPI service and turn errors into readable UI text."""
    headers = dict(kwargs.pop("headers", None) or {})
    # Skip free-tunnel reminder pages (localtunnel/ngrok) for API calls.
    headers.setdefault("bypass-tunnel-reminder", "1")
    headers.setdefault("ngrok-skip-browser-warning", "1")
    token = st.session_state.get("admin_token")
    if token:
        headers.setdefault("X-Admin-Unlock", str(token))
    try:
        response = httpx.request(method, f"{API_BASE}{path}", timeout=30, headers=headers, **kwargs)
        if response.status_code in (401, 428, 429) and not path.startswith("/api/admin/"):
            st.session_state["lock_required"] = True
            st.error("🔒 Dashboard 已鎖定：請先在下方輸入 Admin 密碼解鎖。")
            return None
        response.raise_for_status()
        return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        st.error(f"API {exc.response.status_code}: {detail}")
    except httpx.HTTPError as exc:
        st.error(f"無法連線到 FastAPI ({API_BASE})：{exc}")
    return None


def render_lock_gate() -> None:
    """Unlock box shown when the dashboard lock is engaged."""
    status = api_call("GET", "/api/admin/status")
    if isinstance(status, dict) and not status.get("configured"):
        st.warning("尚未設定 Admin 密碼；請設定至少 12 字元密碼以啟用儀表板。")
    password = st.text_input("Admin 密碼", type="password", key="lock_gate_password")
    if st.button("🔓 解鎖 Dashboard", disabled=not password):
        try:
            if isinstance(status, dict) and not status.get("configured"):
                api_call("POST", "/api/admin/setup", json={"password": password})
            result = api_call("POST", "/api/admin/unlock", json={"password": password})
            if isinstance(result, dict) and result.get("unlock_token"):
                st.session_state["admin_token"] = result["unlock_token"]
                st.session_state["lock_required"] = False
                st.success("已解鎖（15 分鐘無操作會自動上鎖）。")
                st.rerun()
        except Exception:
            pass
    if st.session_state.get("lock_required"):
        st.stop()


def admin_headers() -> dict[str, str]:
    token = st.session_state.get("admin_token")
    return {"X-Admin-Unlock": token} if token else {}


def render_credential_import() -> None:
    with st.expander("🔑 匯入相機密碼（CSV / TXT 批次）"):
        st.caption(
            "每行一組：`ip, username, password, rtsp_path(可省), stream_kind(可省 sub|main)`，"
            "可用逗號／分號／TAB 分隔，第一行標題會自動略過。範例：`192.168.1.101, admin, S3cure!pass, /Streaming/Channels/101`"
        )
        upload = st.file_uploader("選擇 .txt 或 .csv 檔案", type=["txt", "csv"], key="cred_import")
        if upload is not None and st.button("開始匯入"):
            content = upload.getvalue().decode("utf-8-sig", errors="replace")
            result = api_call("POST", "/api/cameras/import-credentials", json={"content": content})
            if result:
                st.success(f"匹配 {result.get('matched', 0)} 台 · 更新 {result.get('updated', 0)} 組憑證 · 錯誤 {len(result.get('errors', []))}")
                for item in result.get("errors", [])[:10]:
                    st.warning(f"第 {item['row']} 行：{item['error']}")


def render_automation() -> None:
    st.subheader("自動化流水線：IP 清單 → 排程掃描 → 自動套密碼 → Live")
    st.caption("設定一次即可：之後掃描發現配對 IP 的相機時會**自動套用帳密**，Live 立刻可播。只對你擁有或獲授權的相機使用。")

    left, right = st.columns(2)

    with left:
        st.markdown("### 1️⃣ 密碼清單（持久保存）")
        st.caption("格式：`ip, username, password, rtsp_path(可省), stream_kind(可省 sub|main)`。密碼以 DPAPI 加密保存。")
        up = st.file_uploader("上傳密碼清單（CSV/TXT）", type=["txt", "csv"], key="book_import")
        replace = st.checkbox("取代現有清單", value=True, key="book_replace")
        if up is not None and st.button("匯入密碼清單", key="book_go"):
            content = up.getvalue().decode("utf-8-sig", errors="replace")
            result = api_call("POST", f"/api/credentials/book/import?replace={str(replace).lower()}", json={"content": content})
            if result:
                st.success(f"新增 {result.get('added', 0)} 筆 · 總計 {result.get('total', 0)} 筆 · 錯誤 {len(result.get('errors', []))}")
                for item in result.get("errors", [])[:8]:
                    st.warning(f"{item.get('row') or '—'}：{item['error']}")
                st.rerun()
        book = api_call("GET", "/api/credentials/book")
        if isinstance(book, dict) and book.get("entries"):
            st.dataframe([
                {"IP/Host": e["target"], "帳號": e["username"], "RTSP 路徑": e["rtsp_path"],
                 "串流": e["stream_kind"], "已配對相機ID": e["camera_id"] or "—"}
                for e in book["entries"]
            ], use_container_width=True)
            b1, b2 = st.columns(2)
            if b1.button("立即套用到相機"):
                result = api_call("POST", "/api/credentials/book/apply")
                if result:
                    st.success(f"已套用 {result.get('matched', 0)} 台：{', '.join(result.get('cameras', [])[:10])}")
            if b2.button("清空密碼清單"):
                api_call("DELETE", "/api/credentials/book")
                st.rerun()
        else:
            st.info("密碼清單目前是空的。")

    with right:
        st.markdown("### 2️⃣ IP 清單（授權目標）")
        st.caption("外部掃描與排程只會碰這份清單裡 enabled 的目標。")
        up2 = st.file_uploader("上傳 IP 清單（CSV/TXT）", type=["txt", "csv"], key="allow_import")
        if up2 is not None and st.button("匯入 IP 清單", key="allow_go"):
            content = up2.getvalue().decode("utf-8-sig", errors="replace")
            fmt = "json" if content.strip().startswith("[") else "csv"
            result = api_call("POST", "/api/external-targets/import", json={"format": fmt, "content": content})
            if result:
                st.success(f"新增 {result.get('created', 0)} · 更新 {result.get('updated', 0)} · 拒絕 {result.get('rejected', 0)}")
                st.rerun()
        targets = api_call("GET", "/api/external-targets") or []
        if targets:
            st.dataframe([
                {"名稱": t["name"], "Host": t["host"], "啟用": "✅" if t["enabled"] else "❌",
                 "最後掃描": (t.get("last_scan") or "—")[:19], "城市": t.get("city") or "—"}
                for t in targets
            ], use_container_width=True)
        else:
            st.info("尚無授權目標。")

        st.markdown("### 3️⃣ 排程自動掃描")
        sched = api_call("GET", "/api/scheduler")
        if isinstance(sched, dict):
            st.caption(f"目前：{'啟用' if sched.get('enabled') else '停用'} · 每 {sched.get('interval_minutes')} 分鐘 · "
                       f"{sched.get('scan_mode')} 模式 · 狀態 {sched.get('state')}")
            cols = st.columns(3)
            interval = cols[0].number_input("間隔（分鐘）", min_value=5, max_value=10080,
                                            value=int(sched.get("interval_minutes") or 60), key="sched_interval")
            mode = cols[1].selectbox("模式", ["quick", "deep"],
                                     index=0 if sched.get("scan_mode") == "quick" else 1, key="sched_mode")
            timeout = cols[2].number_input("單目標逾時（秒）", min_value=2, max_value=300,
                                           value=int(sched.get("target_timeout_seconds") or 15), key="sched_timeout")
            a, b, c = st.columns(3)
            if a.button("啟用排程"):
                api_call("PUT", "/api/scheduler", json={"enabled": True, "interval_minutes": int(interval),
                                                        "scan_mode": mode, "target_timeout_seconds": int(timeout)})
                st.rerun()
            if b.button("立即掃一次"):
                with st.spinner("掃描中…"):
                    result = api_call("POST", "/api/scheduler/run")
                if result:
                    st.success(f"成功 {result.get('succeeded', 0)} · 失敗 {result.get('failed', 0)} · 取消 {result.get('cancelled', 0)}")
            if c.button("停用排程"):
                api_call("PUT", "/api/scheduler", json={"enabled": False, "interval_minutes": int(interval),
                                                        "scan_mode": mode, "target_timeout_seconds": int(timeout)})
                st.rerun()

    st.markdown("### 4️⃣ 看結果（Live）")
    st.markdown(
        "- 單台：Dashboard 分頁每台相機的 **▶ 即時影像** 按鈕\n"
        "- 多畫面：React 儀表板（隧道網址或 127.0.0.1:8080）的 **Live Wall**，支援 1/4/6/9/12/16 宮格\n"
        "- 🔒 只對你擁有或獲授權的相機使用；系統不提供隨機掃描或密碼猜測。"
    )


def render_overview() -> None:
    st.subheader("Camera Dashboard")
    summary = api_call("GET", "/api/dashboard/summary")
    cameras = api_call("GET", "/api/cameras")
    if not summary or cameras is None:
        return
    cols = st.columns(4)
    cols[0].metric("Cameras", summary.get("total_cameras", 0))
    cols[1].metric("Online", summary.get("online", 0))
    cols[2].metric("Offline", summary.get("offline", 0))
    cols[3].metric("go2rtc", summary.get("go2rtc", {}).get("message", "unknown"))
    query = st.text_input("搜尋攝影機", key="camera_search")
    visible = [item for item in cameras if not query or query.lower() in str(item).lower()]
    for camera in visible:
        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"**{camera.get('name', 'Camera')}**  ·  `{camera.get('host') or camera.get('ip')}`")
            location = " · ".join(
                str(value) for value in (camera.get("city"), camera.get("country")) if value
            )
            caption = f"{camera.get('manufacturer', 'Unknown')} / {camera.get('model', 'Unknown')} · {camera.get('status', 'UNKNOWN')}"
            if location:
                caption += f" · 📍 {location}"
            left.caption(caption)
            if camera.get("snapshot_url"):
                left.image(f"{API_BASE}{camera['snapshot_url']}", width=240)
            right.write(camera.get("connection_type", "lan").upper())
            camera_id = camera.get("id")
            if st.button("▶ 即時影像", key=f"live_{camera_id}"):
                st.session_state["live_camera"] = None if st.session_state.get("live_camera") == camera_id else camera_id
                st.rerun()
            if st.session_state.get("live_camera") == camera_id:
                if camera.get("is_mock"):
                    st.info("示範相機（mock）沒有真實串流；新增你真實的相機後即可播放。")
                else:
                    live = api_call("GET", f"/api/cameras/{camera_id}/live")
                    if live and live.get("available") and live.get("player_url"):
                        st.caption(f"串流模式：{live.get('state', 'ready')}")
                        components.iframe(live["player_url"], height=420, scrolling=False)
                    else:
                        reason = live.get("message") if isinstance(live, dict) else "後端無回應"
                        st.warning(f"無法播放：{reason}。需要：①先為此相機設定 RTSP 憑證 ②go2rtc READY ③若從外部觀看，需為 1984 埠開隧道並設定 IPCAM_GO2RTC_API 與 IPCAM_GO2RTC_MODE=hls。")
    geo_points = [
        {"name": item.get("name", "Camera"), "lat": item["latitude"], "lon": item["longitude"]}
        for item in visible
        if item.get("latitude") is not None and item.get("longitude") is not None
    ]
    if geo_points:
        st.subheader("Camera Map")
        st.map(geo_points, latitude="lat", longitude="lon", size=500_000)
    else:
        st.caption("目前沒有帶地理座標的攝影機；對公網目標執行外部掃描後即會出現。")
    render_credential_import()


def render_external_scan() -> None:
    st.subheader("External IP Target")
    st.warning("只掃描你擁有或明確獲授權的單一目標；禁止網際網路大範圍掃描。")
    targets = api_call("GET", "/api/external-targets") or []
    options = {f"{item['name']} · {item['host']}": item for item in targets if item.get("enabled")}
    selected = st.selectbox("已授權目標（可選）", ["手動輸入"] + list(options))
    host = ""
    target_id = None
    if selected != "手動輸入":
        target = options[selected]
        host, target_id = target["host"], target["id"]
    host = st.text_input("Target Host / IP", value=host, placeholder="203.0.113.10 或 camera.example.com:8554")
    mode = st.radio("掃描模式", ["quick", "deep"], horizontal=True)
    if st.button("Start External Scan", type="primary", disabled=not host.strip()):
        payload = {"host": host.strip(), "target_id": target_id, "mode": mode}
        result = api_call("POST", "/api/external-targets/scan", json=payload)
        if result:
            st.success("掃描完成")
            location = result.get("location")
            if location:
                if location.get("is_private"):
                    st.info("📍 私有或保留網段：不會對外查詢地理位置。")
                else:
                    coords = ""
                    if location.get("latitude") is not None and location.get("longitude") is not None:
                        coords = f" · {location['latitude']:.4f}, {location['longitude']:.4f}"
                    st.info(f"📍 {location.get('city') or 'Unknown'}, {location.get('country') or 'Unknown'}{coords} · ISP: {location.get('isp') or 'unknown'}")
            elif result.get("resolved_ip"):
                st.caption("GeoIP 查詢失敗或已達上限，稍後可再試。")
            st.json(result)


def render_authorized_scan() -> None:
    st.subheader("Authorized Public Scan")
    status = api_call("GET", "/api/public-scan") or {}
    st.caption("需先設定本機 Admin 密碼；掃描只允許 allowlist 目標。")
    password = st.text_input("Admin password（至少 12 字元）", type="password")
    if st.button("Set / Unlock Admin", disabled=len(password) < 12):
        if not status.get("admin_configured"):
            api_call("POST", "/api/admin/setup", json={"password": password})
        result = api_call("POST", "/api/admin/unlock", json={"password": password})
        if result and result.get("unlock_token"):
            st.session_state.admin_token = result["unlock_token"]
            st.success("Admin session 已解鎖（短期有效，不會寫入 GitHub）。")
    if st.session_state.get("admin_token"):
        targets = api_call("GET", "/api/external-targets") or []
        enabled = [item for item in targets if item.get("enabled")]
        if enabled:
            selected = st.selectbox("Allowlist target", enabled, format_func=lambda item: f"{item['name']} · {item['host']}")
            if st.button("Enable Public Scan"):
                api_call("PUT", "/api/public-scan", params={"enabled": True}, headers=admin_headers())
            if st.button("Preview Authorized Scan"):
                result = api_call("POST", "/api/public-scan/preview", json={"target_id": selected["id"]}, headers=admin_headers())
                if result:
                    st.json(result)
        else:
            st.info("尚未建立 enabled 的 External Target allowlist。")


def main() -> None:
    st.set_page_config(page_title="IPCAM Dashboard", page_icon="📹", layout="wide")
    override = st.sidebar.text_input(
        "Backend URL 臨時覆寫",
        value=st.session_state.get("api_base_override", ""),
        placeholder=API_BASE_DEFAULT,
        help="隧道網址變了？在這裡貼新網址即可，不用進 Settings 改 Secrets。",
    )
    if override.strip() != st.session_state.get("api_base_override", ""):
        st.session_state["api_base_override"] = override.strip()
        st.rerun()
    set_api_base(st.session_state.get("api_base_override", ""))
    st.sidebar.caption(f"使用中：{API_BASE}")

    st.title("IPCAM Scanner + Multi-Camera Dashboard")
    st.caption(f"FastAPI backend: {API_BASE}")
    health = api_call("GET", "/api/health")
    if health:
        st.success(f"Backend healthy · go2rtc {health.get('go2rtc', {}).get('message', 'unknown')}")
    status = api_call("GET", "/api/admin/status")
    unlocked = (isinstance(status, dict) and status.get("configured")
                and bool(st.session_state.get("admin_token"))
                and not st.session_state.get("lock_required"))
    if not unlocked:
        render_lock_gate()
        st.info("儀表板平時上鎖：解鎖後才會載入相機資料；15 分鐘無操作自動上鎖。")
        return
    header_left, header_right = st.columns([4, 1])
    with header_right:
        if st.button("🔒 Lock now"):
            st.session_state.pop("admin_token", None)
            st.session_state["lock_required"] = False
            st.rerun()
    tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "External Scan", "Authorized Public Scan", "⚙️ 自動化"])
    with tab1:
        render_overview()
    with tab2:
        render_external_scan()
    with tab3:
        render_authorized_scan()
    with tab4:
        render_automation()


if __name__ == "__main__":
    main()
