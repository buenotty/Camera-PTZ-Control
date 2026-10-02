"""Real loopback HTTP/UDP traffic; no church camera or external network needed."""
import base64
import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from PySide6.QtTest import QTest
from src.core.bolin_api import BolinAPIClient, BolinAPIError
from src.core.visca_client import VISCAClient
from src.core.camera_manager import CameraManager, CameraNetworkWorker
from src.core.models import CameraConfig, PTZDirection, WhiteBalanceMode


@contextmanager
def camera_server():
    state = dict(params={'Luminance': 18, 'Contrast': 42, 'Saturation': 42, 'ucHue': 50,
        'eWBMode': 1, 'UnknownSensorField': 77, 'DayNightMode': 2},
        writes=[], udp=[], motion=[], ignore_writes=False, fail_reads=False)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            user, password, payload = body.split('&', 2)
            valid = user == 'ReqUserName=' + base64.b64encode(b'operator').decode() and password == 'ReqUserPwd=' + base64.b64encode(b'test-pass').decode()
            request = json.loads(payload)
            if not valid:
                self.send_response(401)
                self.end_headers()
                return
            command = request['Cmd']
            if command == 'ReqGetVideoParam':
                content = {'nResult': 9} if state['fail_reads'] else {'nResult': 0, 'VideoParam': state['params']}
            elif command == 'ReqSetVideoParam':
                state['writes'].append(request['Content']['VideoParam'])
                if not state['ignore_writes']:
                    state['params'] = dict(request['Content']['VideoParam'])
                content = {'nResult': 0}
            elif command == 'ReqPtzCtrl':
                state['motion'].append(request['Content']['PtzCmd'])
                content = {'nResult': 0}
            else:
                content = {'nResult': 0}
            encoded = json.dumps({'Content': content}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    http_thread = threading.Thread(target=http.serve_forever, daemon=True)
    http_thread.start()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(('127.0.0.1', 0))
    udp.settimeout(0.1)
    closing = threading.Event()
    def receive():
        while not closing.is_set():
            try:
                packet, peer = udp.recvfrom(1024)
            except socket.timeout:
                continue
            payload = packet[8:]
            state['udp'].append(payload)
            if payload == b'\x81\x09\x04\x47\xff':
                response = b'\x90\x50\x02\x00\x00\x00\xff'
                # An old reply with a wrong sequence must not fulfill the inquiry.
                old = b'\x90\x50\x00\x00\x00\x01\xff'
                udp.sendto(b'\x01\x11' + struct.pack('>H', len(old)) + b'\xff\xff\xff\xff' + old, peer)
                udp.sendto(b'\x01\x11' + struct.pack('>H', len(response)) + packet[4:8] + response, peer)
    udp_thread = threading.Thread(target=receive, daemon=True)
    udp_thread.start()
    config = CameraConfig(ip='127.0.0.1', http_port=http.server_port,
        visca_port=udp.getsockname()[1], username='operator', password='test-pass')
    try:
        yield config, state
    finally:
        closing.set()
        udp_thread.join(1)
        udp.close()
        http.shutdown()
        http.server_close()
        http_thread.join(1)


def wait_for(predicate, timeout=2000):
    for _ in range(timeout // 10):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate(), 'Timed out waiting for camera operation'


def test_image_apply_preserves_unknown_fields_and_confirms_readback():
    with camera_server() as (config, state):
        client = BolinAPIClient(config.ip, config.http_port, config.username, config.password)
        assert client.connect()
        worker = CameraNetworkWorker(VISCAClient(config.ip), client)
        results = []
        worker.image_setting_applied.connect(lambda name, ok: results.append((name, ok)))
        worker.update_image_param('hue', 60)
        assert results[-1] == ('hue', True)
        assert state['params']['ucHue'] == 60
        assert 'Hue' not in state['params']
        assert state['params']['UnknownSensorField'] == 77
        assert state['params']['DayNightMode'] == 2
        worker.apply_all_image_settings({'white_balance_mode': WhiteBalanceMode.OUTDOOR})
        assert state['params']['eWBMode'] == 3
        assert state['params']['Saturation'] == 42
        assert results[-1] == ('all', True)
        state['ignore_writes'] = True
        worker.update_image_param('brightness', 90)
        assert results[-1] == ('brightness', False)
        assert state['params']['Luminance'] == 18


def test_failed_image_read_does_not_write_a_stale_cache():
    with camera_server() as (config, state):
        client = BolinAPIClient(config.ip, config.http_port, config.username, config.password)
        assert client.connect()
        state['fail_reads'] = True
        with pytest.raises(BolinAPIError):
            client.update_video_param_fields(Luminance=22)
        assert state['writes'] == []


def test_wrong_http_credentials_are_not_reported_as_authenticated():
    with camera_server() as (config, state):
        client = BolinAPIClient(config.ip, config.http_port, config.username, 'wrong')
        assert not client.connect()
        assert not client.is_connected
        assert not state['writes']


def test_visca_uses_camera_response_and_matches_inquiry_sequence():
    with camera_server() as (config, state):
        client = VISCAClient(config.ip, config.visca_port)
        try:
            assert client.connect()
            assert client.get_zoom_position() == 0x2000
            for direction in [PTZDirection.UP_LEFT, PTZDirection.UP_RIGHT,
                              PTZDirection.DOWN_LEFT, PTZDirection.DOWN_RIGHT]:
                client.pan_tilt(8, 8, direction.value)
            wait_for(lambda: len(state['udp']) == 5)
            assert [packet[6:8] for packet in state['udp'][1:]] == [b'\x01\x01', b'\x02\x01', b'\x01\x02', b'\x02\x02']
        finally:
            client.disconnect()


def test_manager_connects_moves_scales_real_zoom_and_shutdowns(qt_app):
    with camera_server() as (config, state):
        manager = CameraManager()
        try:
            manager.connect(config)
            wait_for(lambda: manager.is_connected)
            wait_for(lambda: manager.current_zoom_level == 0.5)
            assert manager.protocol == 'VISCA + HTTP'
            manager.move_velocity(0.5, 0.5)
            wait_for(lambda: any(p[3:4] == b'\x01' and p[6:8] == b'\x02\x01' for p in state['udp'] if len(p) == 9))
            manager.stop()
            manager.move_velocity(-0.5, 0)
            # Capture the last command after waiting past both redundant stops.
            QTest.qWait(100)
            moves = [p for p in state['udp'] if len(p) == 9]
            assert moves[-1][6:8] == b'\x01\x03'
            manager.zoom_stop()
            manager.zoom_in(3)
            QTest.qWait(80)
            zooms = [p for p in state['udp'] if p[:4] == b'\x81\x01\x04\x07']
            assert zooms[-1][4] == 0x23
        finally:
            manager.shutdown()
            assert not manager._worker_thread.isRunning()


def test_http_mailbox_coalesces_and_restores_other_axis_after_stop(qt_app):
    with camera_server() as (config, state):
        client = BolinAPIClient(config.ip, config.http_port, config.username, config.password)
        assert client.connect()
        worker = CameraNetworkWorker(VISCAClient(config.ip), client)
        worker.queue_motion('ptz', ('Left', 1, 1))
        worker.queue_motion('ptz', ('Right', 8, 8))
        worker.queue_motion('zoom', ('ZoomIn', 3, 0))
        qt_app.processEvents()
        assert state['motion'] == ['Right', 'ZoomIn']
        worker.queue_motion('ptz', ('Stop', 0, 0))
        qt_app.processEvents()
        assert state['motion'][-2:] == ['Stop', 'ZoomIn']


def test_diagnostic_export_has_sensor_fields_without_credentials(tmp_path):
    with camera_server() as (config, state):
        client = BolinAPIClient(config.ip, config.http_port, config.username, config.password)
        assert client.connect()
        worker = CameraNetworkWorker(VISCAClient(config.ip), client)
        output = tmp_path / 'diagnostic.json'
        worker.export_diagnostic(str(output))
        report = json.loads(output.read_text())
        assert report['sensor_values']['Luminance'] == 18
        assert 'ucHue' in report['video_param_fields']
        assert config.password not in output.read_text()
        assert config.username not in output.read_text()
        assert 'UnknownSensorField' not in report['sensor_values']
