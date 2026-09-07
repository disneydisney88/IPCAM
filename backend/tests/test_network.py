import pytest

from app.services.identity import camera_identity, normalize_mac
from app.services.network import validate_private_cidr


@pytest.mark.parametrize("cidr", ["10.2.3.0/24", "172.20.0.0/24", "192.168.88.7/24"])
def test_private_cidr_allowed(cidr):
    assert validate_private_cidr(cidr).is_private


@pytest.mark.parametrize("cidr", ["8.8.8.0/24", "1.1.1.1/32", "2001:db8::/64"])
def test_public_or_ipv6_cidr_rejected(cidr):
    with pytest.raises(ValueError):
        validate_private_cidr(cidr)


def test_huge_scan_rejected():
    with pytest.raises(ValueError, match="too large"):
        validate_private_cidr("10.0.0.0/8")


def test_camera_identity_prefers_stable_key_over_ip():
    first = camera_identity(mac="00-11-22-33-44-55", ip="192.168.1.1")
    second = camera_identity(mac="00:11:22:33:44:55", ip="192.168.1.99")
    assert first == second == "mac:00:11:22:33:44:55"
    assert normalize_mac("0011.2233.4455") == "00:11:22:33:44:55"



def test_detect_interfaces_never_crashes():
    from app.services.network import detect_interfaces

    result = detect_interfaces()
    assert isinstance(result, list)
    for item in result:
        assert item["suggested_cidr"]
