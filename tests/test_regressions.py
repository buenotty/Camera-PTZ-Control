import copy
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from src.core.motion_engine import MotionEngine, MotionConfig, EasingCurve
from src.core.models import CameraConfig, Profile, ImageSettings
from src.core.image_protocol import supported_settings
from src.core.discovery import parse_probe_matches
from src.input.keyboard_handler import KeyboardHandler
from src.ui.image_settings import ImageSettingsPanel
from src.ui.profile_manager import ProfileManager


class Clock:
    def restart(self):
        return 33


@pytest.mark.parametrize('curve', list(EasingCurve))
@pytest.mark.parametrize('zoom', [0.0, 0.5, 1.0])
def test_ramps_reach_target_reverse_and_stop_at_every_zoom(curve, zoom):
    engine = MotionEngine()
    engine.set_config(MotionConfig(easing_curve=curve, zoom_speed_scaling=True, max_ptz_speed=1.0))
    engine.set_zoom_level(zoom)
    engine._elapsed = Clock()
    outputs = []
    engine.velocity_changed.connect(lambda pan, tilt: outputs.append((pan, tilt)))
    engine.set_target_velocity(1, 1)
    for _ in range(15):
        engine._update()
    assert engine._current_pan == 1
    assert outputs[-1][0] > 0
    engine.set_target_velocity(-1, 0)
    for _ in range(15):
        engine._update()
    assert engine._current_pan == -1
    assert outputs[-1][0] < 0
    assert outputs[-1][1] == 0
    engine.set_target_velocity(0, 0)
    for _ in range(15):
        engine._update()
    assert outputs[-1] == (0, 0)
    assert engine._current_pan == 0


def test_speed_limit_applies_to_keyboard_targets():
    engine = MotionEngine()
    engine.set_config(MotionConfig(max_ptz_speed=2 / 24))
    engine._elapsed = Clock()
    output = []
    engine.velocity_changed.connect(lambda pan, tilt: output.append(pan))
    handler = KeyboardHandler()
    handler.set_motion_engine(engine)
    handler.handle_key_press(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))
    for _ in range(15):
        engine._update()
    assert max(output) <= 2 / 24
    handler.clear_all_keys()
    assert output[-1] == 0


def test_control_z_is_undo_not_diagonal_motion():
    handler = KeyboardHandler()
    undo = []
    handler.undo.connect(lambda: undo.append(True))
    assert handler.handle_key_press(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier))
    assert undo == [True]
    assert not handler._pressed_keys


def test_zero_values_and_draft_apply_only_changed_fields(qt_app):
    panel = ImageSettingsPanel()
    panel.set_supported_fields({'brightness', 'saturation', 'gain'})
    panel.update_from_settings(ImageSettings(brightness=0, saturation=0, gain=0))
    assert panel.row_brightness.value() == 0
    assert panel.row_saturation.value() == 0
    assert panel.row_gain.value() == 0
    applied = []
    panel.apply_all_requested.connect(applied.append)
    panel.row_brightness.set_value(25)
    assert not applied
    panel._on_apply_clicked()
    assert applied == [{'brightness': 25}]
    assert not panel.btn_apply.isEnabled()
    assert 'confirmados' not in panel.status.text()
    panel.on_applied('all', False)
    assert 'não confirmou' in panel.status.text()


def test_unknown_isp_modes_are_disabled_and_preserved():
    support = supported_settings({'eWBMode': 99, 'eWDMode': 2, 'Luminance': 30})
    assert support == {'brightness'}


def test_profile_roundtrip_and_export_never_include_password(tmp_path):
    manager = ProfileManager(directory=tmp_path / 'profiles')
    profile = Profile(name='Culto', camera_config=CameraConfig(password='local-secret',
        rtsp_url='rtsp://admin:local-secret@192.0.2.1/stream'), image_settings=ImageSettings(saturation=0, brightness=22))
    manager.save_profile(profile)
    loaded = manager.load_profile('Culto')
    assert loaded.image_settings.saturation == 0
    assert loaded.image_settings.brightness == 22
    assert loaded.camera_config.password == ''
    assert 'local-secret' not in (tmp_path / 'profiles' / 'Culto.json').read_text()
    destination = tmp_path / 'export.json'
    manager.export_profile('Culto', str(destination))
    assert 'local-secret' not in destination.read_text()
    with pytest.raises(ValueError):
        manager.save_profile(Profile(name='../outside'))


def test_rtsp_credentials_are_encoded():
    config = CameraConfig(ip='192.0.2.1', username='a@b', password='p:/?#')
    assert config.stream_url == 'rtsp://a%40b:p%3A%2F%3F%23@192.0.2.1:554/media/video1'


def test_discovery_parses_camera_address_and_name():
    packet = b'''<Envelope xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"><d:ProbeMatches>
    <d:ProbeMatch><d:XAddrs>http://192.0.2.4:8080/onvif/device_service</d:XAddrs>
    <d:Scopes>onvif://www.onvif.org/name/PTZ%20Igreja</d:Scopes></d:ProbeMatch></d:ProbeMatches></Envelope>'''
    cameras = parse_probe_matches(packet)
    assert len(cameras) == 1
    assert cameras[0].ip == '192.0.2.4'
    assert cameras[0].http_port == 8080
    assert cameras[0].name == 'PTZ Igreja'
    assert parse_probe_matches(b'invalid XML') == []
    assert parse_probe_matches(b'<!DOCTYPE x [<!ENTITY y "foo">]><x/>') == []
