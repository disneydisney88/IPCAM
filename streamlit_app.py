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


API_BASE = os.getenv("IPCAM_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def api_call(method: str, path: str, **kwargs: Any) -> Any:
    """Call the local FastAPI service and turn errors into readable UI text."""
    try:
        response = httpx.request(method, f"{API_BASE}{path}", timeout=30, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        st.error(f"API {exc.response.status_code}: {detail}")
    except httpx.HTTPError as exc:
        st.error(f"無法連線到 FastAPI ({API_BASE})：{exc}")
    return None


def admin_headers() -> dict[str, str]:
    token = st.session_state.get("admin_token")
    return {"X-Admin-Unlock": token} if token else {}


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
            right.write(camera.get("connection_type", "lan").upper())
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
    st.title("IPCAM Scanner + Multi-Camera Dashboard")
    st.caption(f"FastAPI backend: {API_BASE}")
    health = api_call("GET", "/api/health")
    if health:
        st.success(f"Backend healthy · go2rtc {health.get('go2rtc', {}).get('message', 'unknown')}")
    tab1, tab2, tab3 = st.tabs(["Dashboard", "External Scan", "Authorized Public Scan"])
    with tab1:
        render_overview()
    with tab2:
        render_external_scan()
    with tab3:
        render_authorized_scan()


if __name__ == "__main__":
    main()
