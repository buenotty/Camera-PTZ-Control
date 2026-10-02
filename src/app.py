import sys
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from src.core.camera_manager import CameraManager
from src.core.motion_engine import MotionEngine
from src.core.models import CameraConfig, Profile, Preset
from src.input.keyboard_handler import KeyboardHandler
from src.input.mouse_handler import MouseHandler
from src.input.gamepad_handler import GamepadHandler
from src.ui.main_window import MainWindow
from src.utils.settings import SettingsManager
from src.utils.logger import get_logger

logger = get_logger('app')


class PTZControlApp(QObject):
    def __init__(self):
        super().__init__()
        self._qt_app = QApplication.instance() or QApplication(sys.argv)
        self._qt_app.setApplicationName('PTZ Control')
        self._qt_app.setOrganizationName('PTZ Control')
        self._camera_manager = CameraManager()
        self._motion_engine = MotionEngine()
        self._keyboard_handler = KeyboardHandler()
        self._mouse_handler = MouseHandler()
        self._keyboard_handler.set_motion_engine(self._motion_engine)
        self._mouse_handler.set_motion_engine(self._motion_engine)
        self._window = MainWindow()
        self._window.set_keyboard_handler(self._keyboard_handler)
        self._gamepad = GamepadHandler(self._motion_engine, active=lambda: self._window.isActiveWindow() and self._camera_manager.is_connected and QApplication.activeModalWidget() is None)
        self._closed = False
        self._config = CameraConfig.from_dict(SettingsManager().get('camera', {}))
        self._config.password = ''
        self._window._camera_config = self._config
        self._wire()
        self._window.update_connection_status(False)
        self._window.get_focus_controls().setEnabled(False)
        self._motion_engine.start()
        self._qt_app.aboutToQuit.connect(self.shutdown)

    def _wire(self):
        manager, engine, window = self._camera_manager, self._motion_engine, self._window
        ptz, video, image = window.get_ptz_controls(), window.get_video_panel(), window.get_image_settings()
        engine.velocity_changed.connect(manager.move_velocity)
        engine.zoom_velocity_changed.connect(self._on_zoom_velocity)
        engine.speed_info_updated.connect(window.update_velocity_info)
        manager.zoom_level_changed.connect(engine.set_zoom_level)
        manager.zoom_level_changed.connect(ptz.set_current_zoom_level)
        manager.zoom_available.connect(ptz.set_zoom_available)
        ptz.set_motion_engine(engine)
        ptz.input_combo.currentIndexChanged.connect(self._input_mode_changed)
        self._gamepad.status_changed.connect(ptz.gamepad_status.setText)
        for axis in ptz.gamepad_axes:
            axis.valueChanged.connect(self._gamepad_axes_changed)
        video.mouse_drag_started.connect(self._mouse_handler.on_drag_started)
        video.mouse_drag_moved.connect(lambda p, t: engine.set_mouse_velocity(p, t) if ptz.input_combo.currentIndex() != 2 else None)
        video.mouse_drag_ended.connect(self._mouse_handler.on_drag_ended)
        video.mouse_scroll.connect(lambda d: self._mouse_handler.on_scroll(d) if ptz.input_combo.currentIndex() != 2 else None)
        video.resized.connect(self._mouse_handler.set_viewport_size)
        video.playback_error.connect(self._on_error)
        focus = window.get_focus_controls()
        focus.focus_mode_changed.connect(self._on_toggle_focus)
        focus.focus_near_start.connect(lambda: self._focus('focus_near'))
        focus.focus_far_start.connect(lambda: self._focus('focus_far'))
        focus.focus_stop.connect(lambda: self._focus('focus_stop'))
        focus.focus_one_push.connect(lambda: self._focus('focus_one_push'))
        image.apply_all_requested.connect(manager.apply_all_image_settings)
        image.read_from_camera.connect(manager.read_image_settings)
        manager.image_settings_read.connect(image.update_from_settings)
        manager.image_support_changed.connect(image.set_supported_fields)
        manager.image_setting_applied.connect(image.on_applied)
        presets = window.get_preset_manager()
        presets.preset_recalled.connect(self._recall_preset)
        presets.preset_saved.connect(self._save_preset)
        presets.preset_deleted.connect(self._delete_preset)
        presets.preset_renamed.connect(self._rename_preset)
        recording = window.get_recording_controls()
        recording.recording_toggled.connect(self._on_toggle_recording)
        recording.snapshot_requested.connect(self._on_snapshot)
        video.recording_changed.connect(recording.set_recording)
        profiles = window.get_profile_manager()
        profiles.manager.profile_loaded.connect(self._on_profile_loaded)
        profiles.save_requested.connect(self._save_profile)
        kb = self._keyboard_handler
        kb.emergency_stop.connect(self._emergency_stop)
        kb.preset_recall.connect(self._recall_preset)
        kb.preset_save.connect(lambda n: self._save_preset(n, f'Posição {n}'))
        kb.toggle_recording.connect(lambda: self._on_toggle_recording(not video.is_recording()))
        kb.capture_snapshot.connect(self._on_snapshot)
        kb.toggle_fullscreen.connect(window._toggle_fullscreen)
        kb.show_shortcuts.connect(window._show_keyboard_shortcuts)
        kb.read_camera_settings.connect(manager.read_image_settings)
        kb.undo.connect(image._do_undo)
        kb.redo.connect(image._do_redo)
        kb.toggle_grid.connect(lambda: window.action_toggle_grid.setChecked(not window.action_toggle_grid.isChecked()))
        kb.toggle_focus_mode.connect(focus._on_toggle_mode)
        kb.focus_near.connect(lambda: self._focus('focus_near'))
        kb.focus_far.connect(lambda: self._focus('focus_far'))
        kb.focus_stop_signal.connect(lambda: self._focus('focus_stop'))
        window.emergency_requested.connect(self._emergency_stop)
        window.connection_requested.connect(self._on_connection_requested)
        window.disconnect_requested.connect(self._disconnect)
        window.diagnostic_requested.connect(self._export_diagnostic)
        manager.diagnostic_saved.connect(lambda path, ok: window.statusBar().showMessage(f"Diagnóstico salvo em {path}" if ok else "Falha ao salvar diagnóstico.", 10000))
        manager.connection_changed.connect(self._on_connection_changed)
        manager.error_occurred.connect(self._on_error)
        manager.preset_finished.connect(self._on_preset_finished)

    def run(self):
        self._window.show()
        return self._qt_app.exec()

    def _emergency_stop(self):
        self._gamepad.suspend()
        self._keyboard_handler._pressed_keys.clear()
        self._keyboard_handler._key_timestamps.clear()
        self._mouse_handler._zoom_stop_timer.stop()
        self._window.get_ptz_controls().joystick.is_dragging = False
        self._window.get_ptz_controls().joystick.reset_joystick()
        self._window.get_video_panel()._overlay._dragging = False
        self._motion_engine.emergency_stop()
        self._focus('focus_stop')

    def _input_mode_changed(self, index):
        self._emergency_stop()
        self._keyboard_handler.motion_enabled = index != 2
        self._gamepad.set_enabled(index == 2)

    def _gamepad_axes_changed(self):
        self._gamepad.axes = tuple(axis.value() for axis in self._window.get_ptz_controls().gamepad_axes)
        self._emergency_stop()

    def _on_connection_requested(self, config):
        self._emergency_stop()
        self._window.get_video_panel().stop()
        self._config = config
        self._window._camera_config = config
        # Only non-secret preferences persist; passwords stay in memory.
        SettingsManager().set('camera', config.to_dict())
        self._window.camera_badge.setText('●  Conectando…')
        self._window.connect_button.setEnabled(False)
        self._camera_manager.connect(config)

    def _on_connection_changed(self, connected):
        window = self._window
        window.connect_button.setEnabled(True)
        window.update_connection_status(connected, self._config.ip, self._camera_manager.protocol)
        window.get_focus_controls().setEnabled(connected and self._camera_manager._worker.visca_ready)
        if connected:
            window.get_video_panel().play(self._config.stream_url)
            # Slots 1..9 are shortcuts, not a claim that those presets exist.
            data = SettingsManager().get('presets.' + self._config.ip, [])
            window.get_preset_manager().load_presets([Preset.from_dict(p) for p in data])
        else:
            self._emergency_stop()
            window.get_video_panel().stop()

    def _disconnect(self):
        self._emergency_stop()
        self._camera_manager.disconnect()
        self._window.get_video_panel().stop()
        self._window.update_connection_status(False)

    def _on_zoom_velocity(self, value):
        if value > 0:
            self._camera_manager.zoom_in(max(1, round(value * 7)))
        elif value < 0:
            self._camera_manager.zoom_out(max(1, round(-value * 7)))
        else:
            self._camera_manager.zoom_stop()

    def _focus(self, command):
        manager = self._camera_manager
        if manager.is_connected and manager._worker.visca_ready:
            getattr(manager._visca, command)()

    def _on_toggle_focus(self, mode):
        self._focus('focus_auto' if mode == 'auto' else 'focus_manual')

    def _persist_presets(self):
        cards = self._window.get_preset_manager().cards
        SettingsManager().set('presets.' + self._config.ip, [card.preset.to_dict() for card in cards.values()])

    def _save_preset(self, number, name):
        if not self._camera_manager.is_connected:
            return
        self._emergency_stop()
        self._camera_manager.save_preset(number, name)


    def _recall_preset(self, number):
        self._emergency_stop()
        self._camera_manager.recall_preset(number)

    def _delete_preset(self, number):
        self._emergency_stop()
        self._camera_manager.delete_preset(number)


    def _on_preset_finished(self, action, number, name, success):
        if not success:
            return
        panel = self._window.get_preset_manager()
        if action == 'save':
            panel.add_preset(Preset(number=number, name=name))
            self._persist_presets()
        elif action == 'delete':
            panel.remove_preset(number)
            self._persist_presets()
        else:
            panel.set_active_preset(number)
        self._window.statusBar().showMessage('Comando de preset aceito via HTTP.' if self._camera_manager._bolin.is_connected else
            'Comando enviado via VISCA. Confira a posição na prévia.', 5000)

    def _rename_preset(self, number, name):
        self._persist_presets()

    def _save_profile(self, name):
        profile = Profile(name=name, camera_config=self._config,
            image_settings=self._window.get_image_settings().get_current_settings())
        try:
            self._window.get_profile_manager().manager.save_profile(profile)
            self._window.statusBar().showMessage('Perfil salvo sem senha.', 5000)
        except (ValueError, OSError):
            self._on_error('Nome de perfil inválido ou pasta indisponível.')

    def _on_profile_loaded(self, profile):
        self._window.get_image_settings().update_from_settings(profile.image_settings, from_camera=False)
        self._window._right_tabs.setCurrentIndex(1)

    def _on_toggle_recording(self, active):
        video = self._window.get_video_panel()
        if active:
            path = SettingsManager().settings_dir / 'recordings' / f'{datetime.now():%Y%m%d_%H%M%S}.mkv'
            video.start_recording(str(path))
        else:
            video.stop_recording()

    def _on_snapshot(self):
        path = SettingsManager().settings_dir / 'snapshots' / f'{datetime.now():%Y%m%d_%H%M%S}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        video = self._window.get_video_panel()
        if video.is_playing() and video._video_frame.frame.save(str(path)):
            self._window.statusBar().showMessage(f'Captura salva em {path}', 5000)
        else:
            self._on_error('A captura exige vídeo conectado.')

    def _export_diagnostic(self):
        path, _ = QFileDialog.getSaveFileName(self._window, 'Exportar diagnóstico sem credenciais',
            'ptz-diagnostico.json', 'JSON (*.json)')
        if path:
            self._camera_manager.export_diagnostic(path)

    def _on_error(self, message):
        logger.warning(message)
        self._window.statusBar().showMessage(message, 15000)

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self._qt_app.removeEventFilter(self._window)
        self._emergency_stop()
        self._gamepad.shutdown()
        self._motion_engine.stop()
        self._camera_manager.shutdown()
        self._window.get_video_panel().shutdown()
