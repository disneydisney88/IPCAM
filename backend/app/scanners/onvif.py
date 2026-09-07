from __future__ import annotations

import asyncio
import re
import socket
import uuid
from dataclasses import dataclass, asdict
from xml.etree import ElementTree


WS_DISCOVERY_MESSAGE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header><w:MessageID>uuid:{message_id}</w:MessageID>
 <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
 <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>
 <e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>
</e:Envelope>"""


def _first_text(root: ElementTree.Element, suffix: str) -> str | None:
    for element in root.iter():
        if element.tag.endswith(suffix) and element.text:
            return element.text.strip()
    return None


def parse_onvif_probe(xml_text: str) -> list[dict[str, str | list[str] | None]]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    matches = [node for node in root.iter() if node.tag.endswith("ProbeMatch")]
    results = []
    for match in matches:
        xaddrs_text = _first_text(match, "XAddrs") or ""
        address = _first_text(match, "Address")
        scopes = _first_text(match, "Scopes")
        results.append({
            "uuid": address.removeprefix("urn:uuid:") if address else None,
            "xaddrs": xaddrs_text.split(),
            "scopes": scopes.split() if scopes else [],
        })
    return results


async def ws_discover(timeout: float = 2.0) -> list[dict[str, str | list[str] | None]]:
    message = WS_DISCOVERY_MESSAGE.format(message_id=uuid.uuid4()).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    found: dict[str, dict[str, str | list[str] | None]] = {}
    try:
        await loop.sock_sendto(sock, message, ("239.255.255.250", 3702))
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                data, _ = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), deadline - loop.time())
            except (asyncio.TimeoutError, OSError):
                break
            for item in parse_onvif_probe(data.decode(errors="replace")):
                key = str(item.get("uuid") or item.get("xaddrs"))
                found[key] = item
    except OSError:
        return []
    finally:
        sock.close()
    return list(found.values())

