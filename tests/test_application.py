from unittest.mock import Mock
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from src.app import PTZControlApp
from test_camera_integration import camera_server, wait_for


def test_full_application_connects_applies_image_and_stops(qt_app):
    app = PTZControlApp()
    app._window.show()
    video = app._window.get_video_panel()
    video.play = Mock()  # RTSP is independently validated by check-video.py.
    try:
        assert not app._camera_manager.is_connected
        assert not app._window.get_ptz_controls().isEnabled()
        with camera_server() as (config, state):
            app._on_connection_requested(config)
            wait_for(lambda: app._camera_manager.is_connected)
            wait_for(lambda: app._window.get_image_settings().row_brightness.value() == 18)
            video.play.assert_called_with(config.stream_url)
            assert app._window.get_ptz_controls().isEnabled()
            image = app._window.get_image_settings()
            image.row_brightness.set_value(35)
            image._on_apply_clicked()
            wait_for(lambda: state['params']['Luminance'] == 35)
            wait_for(lambda: 'confirmados' in image.status.text())
            ptz = app._window.get_ptz_controls()
            ptz._on_dpad_pressed(1, 1)
            wait_for(lambda: any(len(p) == 9 and p[6:8] == b'\x02\x01' for p in state['udp']))
            app._window.emergency_button.click()
            assert app._motion_engine._target_pan == 0
            assert app._motion_engine._target_zoom == 0
            wait_for(lambda: any(len(p) == 9 and p[6:8] == b'\x03\x03' for p in state['udp']))
            app._disconnect()
            wait_for(lambda: not app._camera_manager._worker.visca_ready)
            assert not app._window.get_ptz_controls().isEnabled()
    finally:
        app.shutdown()
        app._window.close()
        assert not app._camera_manager._worker_thread.isRunning()
        assert not app._gamepad.timer.isActive()


def test_optional_vlc_missing_does_not_prevent_opening_window(qt_app, monkeypatch):
    import src.ui.video_panel as video_module
    monkeypatch.setattr(video_module, 'vlc', None)
    app = PTZControlApp()
    try:
        app._window.show()
        assert app._window.get_video_panel()._player is None
        assert app._window.isVisible()
        app._window._toggle_theme()
        assert '#eef3f7' in qt_app.styleSheet()
    finally:
        app.shutdown()
        app._window.close()
