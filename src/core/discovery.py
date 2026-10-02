"""ONVIF WS-Discovery on the local network (discovery only, not ONVIF control)."""
from dataclasses import dataclass
import socket
import time
import uuid
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class DiscoveredCamera:
    ip: str
    name: str
    http_port: int = 80


def parse_probe_matches(packet):
    if b'<!DOCTYPE' in packet.upper() or b'<!ENTITY' in packet.upper():
        return []
    try:
        root = ET.fromstring(packet)
    except ET.ParseError:
        return []
    found = []
    for match in root.iter():
        if match.tag.rsplit('}', 1)[-1] != 'ProbeMatch':
            continue
        fields = {child.tag.rsplit('}', 1)[-1]: child.text or '' for child in match}
        name = 'Câmera ONVIF'
        for scope in fields.get('Scopes', '').split():
            if '/name/' in scope:
                name = unquote(scope.split('/name/', 1)[1])
        for address in fields.get('XAddrs', '').split():
            try:
                url = urlsplit(address)
                socket.inet_aton(url.hostname or '')
                port = url.port or (443 if url.scheme == 'https' else 80)
                if url.scheme == 'http':
                    found.append(DiscoveredCamera(url.hostname, name, port))
            except (ValueError, OSError):
                continue
    return found


def discover_cameras(timeout=3.0, cancelled=lambda: False):
    probe = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
        xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
        xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
        xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
      <s:Header><a:MessageID>uuid:{uuid.uuid4()}</a:MessageID>
      <a:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
      <a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action></s:Header>
      <s:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></s:Body>
    </s:Envelope>'''.encode()
    cameras = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.bind(('', 0))
        sock.settimeout(0.2)
        sock.sendto(probe, ('239.255.255.250', 3702))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not cancelled():
            try:
                packet, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            for camera in parse_probe_matches(packet):
                cameras[camera.ip] = camera
    return sorted(cameras.values(), key=lambda camera: camera.ip)
