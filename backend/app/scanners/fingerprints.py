from __future__ import annotations

from pydantic import BaseModel


class BrandSignature(BaseModel):
    brand_name: str
    server_headers: list[str] = []
    title_keywords: list[str] = []
    realm_keywords: list[str] = []
    default_rtsp_paths: list[str] = []
    snapshot_endpoints: list[str] = []


FINGERPRINT_DATABASE: dict[str, BrandSignature] = {
    "hikvision": BrandSignature(
        brand_name="Hikvision",
        server_headers=["Hikvision-Webs", "App-webs", "DNVRS-Webs", "web-version"],
        title_keywords=["Hikvision", "HiLook", "EZVIZ", "Embedded Net DVR"],
        realm_keywords=["Hikvision", "DS-", "DVR", "NVR"],
        default_rtsp_paths=["/Streaming/Channels/101", "/Streaming/Channels/102", "/h264/ch1/main/av_stream"],
        snapshot_endpoints=["/ISAPI/Streaming/channels/101/picture", "/onvif-http/snapshot"],
    ),
    "dahua": BrandSignature(
        brand_name="Dahua",
        server_headers=["Dahua", "WEB SERVICE", "NETSurveillance", "DH-"],
        title_keywords=["Dahua", "Imou", "Amcrest", "WEB SERVICE"],
        realm_keywords=["Dahua", "DH-", "General"],
        default_rtsp_paths=["/cam/realmonitor?channel=1&subtype=0", "/cam/realmonitor?channel=1&subtype=1"],
        snapshot_endpoints=["/cgi-bin/snapshot.cgi", "/onvif/snapshot"],
    ),
    "axis": BrandSignature(
        brand_name="Axis Communications",
        server_headers=["AXIS Video Server", "Boa/0.94", "Axis"],
        title_keywords=["AXIS", "Network Camera"],
        realm_keywords=["AXIS", "Network Camera"],
        default_rtsp_paths=["/axis-media/media.amp"],
        snapshot_endpoints=["/axis-cgi/jpg/image.cgi", "/jpg/image.jpg"],
    ),
    "uniview": BrandSignature(
        brand_name="Uniview (UNV)",
        server_headers=["Uniview", "UNV-Web", "Network Video Server"],
        title_keywords=["Uniview", "UNV", "Network Video Server"],
        realm_keywords=["UNV", "Uniview"],
        default_rtsp_paths=["/media/video1", "/unicast/c1/s0/live"],
        snapshot_endpoints=["/images/snapshot.jpg", '/cgi-bin/main-cgi?json={"cmd":259}'],
    ),
    "xiongmai": BrandSignature(
        brand_name="Xiongmai (XMeye)",
        server_headers=["uc-httpd", "Sofia", "NETSurveillance"],
        title_keywords=["NETSurveillance", "DVR Web Client", "IPCAM"],
        realm_keywords=["Sofia", "NETSurveillance"],
        default_rtsp_paths=["/live/ch0", "/stream0"],
        snapshot_endpoints=["/webcapture.jpg?command=snap&channel=1", "/cgi-bin/net_jpeg.cgi?ch=1"],
    ),
    "reolink": BrandSignature(
        brand_name="Reolink",
        server_headers=["Reolink", "nginx"],
        title_keywords=["Reolink", "Reolink Camera"],
        realm_keywords=["Reolink"],
        default_rtsp_paths=["/h264Preview_01_main", "/h265Preview_01_main"],
        snapshot_endpoints=["/cgi-bin/api.cgi?cmd=Snap&channel=0"],
    ),
    "vivotek": BrandSignature(
        brand_name="Vivotek",
        server_headers=["VIVOTEK", "Network Camera Vivotek"],
        title_keywords=["Vivotek", "Network Camera"],
        realm_keywords=["Vivotek"],
        default_rtsp_paths=["/live.sdp", "/live/media.amp"],
        snapshot_endpoints=["/cgi-bin/viewer/video.jpg"],
    ),
}
