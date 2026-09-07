from app.scanners.onvif import parse_onvif_probe
from app.services.ffprobe import parse_ffprobe


def test_onvif_probe_parser():
    xml = """<Envelope xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"><Body><d:ProbeMatches><d:ProbeMatch><a:EndpointReference><a:Address>urn:uuid:camera-123</a:Address></a:EndpointReference><d:Scopes>onvif://www.onvif.org/type/video_encoder onvif://www.onvif.org/name/Lobby</d:Scopes><d:XAddrs>http://192.168.1.20/onvif/device_service</d:XAddrs></d:ProbeMatch></d:ProbeMatches></Body></Envelope>"""
    result = parse_onvif_probe(xml)
    assert result[0]["uuid"] == "camera-123"
    assert result[0]["xaddrs"] == ["http://192.168.1.20/onvif/device_service"]


def test_ffprobe_parser():
    payload = {"streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "25/1", "bit_rate": "2048000"},
        {"codec_type": "audio", "codec_name": "aac"},
    ], "format": {}}
    result = parse_ffprobe(payload, 123.456)
    assert result == {"codec": "H264", "width": 1920, "height": 1080, "fps": 25.0,
                      "bitrate": 2048000, "audio_codec": "AAC", "latency_ms": 123.5, "validated": True}

