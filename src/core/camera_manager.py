"""Camera orchestration: network I/O belongs to the worker, not the UI."""
import threading
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer, QMetaObject, Qt
from src.core.models import CameraConfig, PTZDirection
from src.core.visca_client import VISCAClient
from src.core.bolin_api import BolinAPIClient
from src.core.image_protocol import encode_setting, decode_settings, supported_settings


class CameraNetworkWorker(QObject):
    error = Signal(str)
    connection_status = Signal(bool)
    image_settings_read = Signal(object)
    image_support = Signal(object)
    image_setting_applied = Signal(str, bool)
    zoom_position = Signal(object)
    motion_ready = Signal()
    preset_finished = Signal(str, int, str, bool)
    diagnostic_saved = Signal(str, bool)

    def __init__(self, visca, bolin):
        super().__init__()
        self.visca, self.bolin = visca, bolin
        self.visca_ready = False
        self._lock = threading.Lock()
        self._pending = {}
        self._http_state = {}
        self._scheduled = False
        self.motion_ready.connect(self.flush_motion, Qt.ConnectionType.QueuedConnection)

    def queue_motion(self, channel, command):
        # Thread-safe mailbox: retain the latest intent instead of queuing
        # 30 HTTP calls per second, including obsolete movement commands.
        with self._lock:
            self._pending[channel] = command
            schedule = not self._scheduled
            self._scheduled = True
        if schedule:
            self.motion_ready.emit()

    @Slot()
    def flush_motion(self):
        with self._lock:
            commands = self._pending
            self._pending = {}
            self._http_state.update(commands)
            state = dict(self._http_state)
            self._scheduled = False
        if not self.bolin.is_connected:
            return
        stopping = any(value[0] == 'Stop' for value in commands.values())
        if stopping:
            if not self.bolin.ptz_stop():
                self.error.emit('A câmera não confirmou a parada HTTP.')
            commands = {channel: value for channel, value in state.items() if value[0] != 'Stop'}
        for command, pan_speed, tilt_speed in commands.values():
            if not self.bolin.ptz_ctrl(command, pan_speed, tilt_speed):
                self.error.emit('A câmera recusou um comando de movimento HTTP.')

    @Slot(object)
    def connect_camera(self, config):
        self.disconnect_camera(notify=False)
        self.visca.ip, self.visca.port = config.ip, config.visca_port
        self.bolin.ip, self.bolin.port = config.ip, config.http_port
        self.bolin.username, self.bolin.password = config.username, config.password
        position = None
        if self.visca.connect():
            position = self.visca.get_zoom_position()
        self.visca_ready = position is not None
        if not self.visca_ready:
            self.visca.disconnect()
        http_ready = self.bolin.connect()
        connected = self.visca_ready or http_ready
        self.connection_status.emit(connected)
        self.zoom_position.emit(position)
        if http_ready:
            self.read_image_settings()
        else:
            self.image_support.emit(set())
        if not connected:
            self.error.emit('Sem resposta compatível. Confira IP, portas, credenciais e rede local.')

    @Slot()
    def disconnect_camera(self, notify=True):
        with self._lock:
            self._pending.clear()
            self._http_state.clear()
        if self.visca_ready:
            self.visca.stop()
            self.visca.zoom_stop()
            self.visca.focus_stop()
        elif self.bolin.is_connected:
            self.bolin.ptz_stop()
        self.visca_ready = False
        self.visca.disconnect()
        self.bolin.disconnect()
        if notify:
            self.connection_status.emit(False)
        self.image_support.emit(set())

    @Slot()
    def read_image_settings(self):
        try:
            if not self.bolin.is_connected:
                raise ValueError('Ajustes de imagem exigem a API HTTP Bolin/GXX-ISP.')
            params = self.bolin.get_video_param()
            self.image_support.emit(supported_settings(params))
            self.image_settings_read.emit(decode_settings(params))
        except Exception:
            self.image_support.emit(set())
            self.error.emit('Não foi possível ler os ajustes de imagem. Confira compatibilidade e autenticação.')

    def _apply(self, name, changes):
        try:
            if not self.bolin.is_connected:
                raise ValueError('API HTTP indisponível')
            current = self.bolin.get_video_param()
            fields = {}
            for key, value in changes.items():
                fields.update(encode_setting(key, value, current))
            desired = dict(current, **fields)
            if not self.bolin.set_video_param(desired):
                raise ValueError('Comando recusado')
            actual = self.bolin.get_video_param()
            ok = all(str(actual.get(key)) == str(value) for key, value in fields.items())
            self.image_settings_read.emit(decode_settings(actual))
            self.image_setting_applied.emit(name, ok)
            if not ok:
                self.error.emit('A câmera não confirmou os valores solicitados. Os valores reais foram recarregados.')
        except Exception:
            self.image_setting_applied.emit(name, False)
            self.error.emit('Falha ao aplicar imagem: ajuste não suportado, autenticação ou comunicação.')

    @Slot(str, object)
    def update_image_param(self, name, value):
        self._apply(name, {name: value})

    @Slot(object)
    def apply_all_image_settings(self, settings):
        try:
            params = self.bolin.get_video_param()
            actual = decode_settings(params)
            changes = dict(settings) if isinstance(settings, dict) else {name: getattr(settings, name) for name in supported_settings(params) if getattr(settings, name) != getattr(actual, name)}
            if not changes:
                raise ValueError('Nenhum ajuste suportado')
            self._apply('all', changes)
        except Exception:
            self.image_setting_applied.emit('all', False)
            self.error.emit('Não foi possível aplicar o perfil de imagem.')

    @Slot()
    def poll_zoom(self):
        if self.visca_ready:
            self.zoom_position.emit(self.visca.get_zoom_position())

    @Slot(int, str)
    def save_preset(self, number, name):
        self._preset('save', number, name)

    @Slot(int)
    def recall_preset(self, number):
        self._preset('recall', number)
        self.poll_zoom()

    @Slot(int)
    def delete_preset(self, number):
        self._preset('delete', number)

    def _preset(self, action, number, name=''):
        ok = False
        if self.bolin.is_connected:
            if action == 'save':
                ok = self.bolin.set_preset(number, name)
            elif action == 'recall':
                ok = self.bolin.recall_preset(number)
            else:
                ok = self.bolin.delete_preset(number)
        elif self.visca_ready:
            {'save': self.visca.set_preset, 'recall': self.visca.recall_preset,
             'delete': self.visca.clear_preset}[action](number)
            ok = True  # VISCA command sent; no claim of physical completion.
        self.preset_finished.emit(action, number, name, ok)
        if not ok:
            self.error.emit('A câmera não confirmou a operação com o preset.')

    @Slot(str)
    def export_diagnostic(self, path):
        from src.core.image_protocol import FIELDS
        report = {'format': 1, 'visca_response_confirmed': self.visca_ready,
                  'http_authenticated': self.bolin.is_connected, 'video_param_fields': [], 'sensor_values': {}}
        try:
            if self.bolin.is_connected:
                params = self.bolin.get_video_param()
                report['video_param_fields'] = sorted(params)
                known = {key for aliases in FIELDS.values() for key in aliases}
                report['sensor_values'] = {key: value for key, value in params.items()
                    if key in known and isinstance(value, (int, float, bool))}
            Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            self.diagnostic_saved.emit(path, True)
        except Exception:
            self.diagnostic_saved.emit(path, False)
            self.error.emit('Não foi possível exportar o diagnóstico. Confira a conexão e a pasta de destino.')

    @Slot(str)
    def capture_thumbnail(self, path):
        try:
            self.bolin.capture_snapshot(path)
        except Exception:
            self.error.emit('Falha na captura de imagem pela câmera.')


class CameraManager(QObject):
    connection_changed = Signal(bool)
    error_occurred = Signal(str)
    image_settings_read = Signal(object)
    image_support_changed = Signal(object)
    image_setting_applied = Signal(str, bool)
    zoom_level_changed = Signal(float)
    zoom_available = Signal(bool)
    preset_finished = Signal(str, int, str, bool)
    diagnostic_saved = Signal(str, bool)
    _req_diagnostic = Signal(str)
    _req_connect = Signal(object)
    _req_disconnect = Signal()
    _req_read_image = Signal()
    _req_update_image_param = Signal(str, object)
    _req_apply_all_image = Signal(object)
    _req_poll_zoom = Signal()
    _req_save_preset = Signal(int, str)
    _req_recall_preset = Signal(int)
    _req_delete_preset = Signal(int)
    _req_capture_thumb = Signal(str)

    def __init__(self):
        super().__init__()
        self._visca = VISCAClient('127.0.0.1')
        self._bolin = BolinAPIClient('127.0.0.1')
        self._config = CameraConfig()
        self._connected = False
        self._current_zoom_level = 0.0
        self._last_motion = None
        self._last_zoom = None
        self._ptz_generation = 0
        self._zoom_generation = 0
        self._shutdown = False
        self._poll_pending = False
        self._worker_thread = QThread(self)
        self._worker = CameraNetworkWorker(self._visca, self._bolin)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self.error_occurred)
        self._worker.connection_status.connect(self._handle_connection_status)
        self._worker.image_settings_read.connect(self.image_settings_read)
        self._worker.image_support.connect(self.image_support_changed)
        self._worker.image_setting_applied.connect(self.image_setting_applied)
        self._worker.zoom_position.connect(self._on_zoom_position)
        self._worker.preset_finished.connect(self.preset_finished)
        self._worker.diagnostic_saved.connect(self.diagnostic_saved)
        for signal, slot in (
            (self._req_connect, self._worker.connect_camera),
            (self._req_diagnostic, self._worker.export_diagnostic),
            (self._req_disconnect, self._worker.disconnect_camera),
            (self._req_read_image, self._worker.read_image_settings),
            (self._req_update_image_param, self._worker.update_image_param),
            (self._req_apply_all_image, self._worker.apply_all_image_settings),
            (self._req_poll_zoom, self._worker.poll_zoom),
            (self._req_save_preset, self._worker.save_preset),
            (self._req_recall_preset, self._worker.recall_preset),
            (self._req_delete_preset, self._worker.delete_preset),
            (self._req_capture_thumb, self._worker.capture_thumbnail),
        ):
            signal.connect(slot)
        self._worker_thread.start()
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setInterval(750)
        self._zoom_timer.timeout.connect(self._poll_zoom)

    @property
    def is_connected(self):
        return self._connected

    @property
    def protocol(self):
        return 'VISCA + HTTP' if self._worker.visca_ready and self._bolin.is_connected else ('VISCA' if self._worker.visca_ready else 'HTTP')

    @property
    def current_zoom_level(self):
        return self._current_zoom_level

    @Slot(bool)
    def _handle_connection_status(self, connected):
        self._connected = connected
        self._last_motion = self._last_zoom = None
        self._poll_pending = False
        if connected and self._worker.visca_ready:
            self._zoom_timer.start()
        else:
            self._zoom_timer.stop()
        self.connection_changed.emit(connected)

    @Slot(object)
    def _on_zoom_position(self, position):
        self._poll_pending = False
        # VISCA's typical optical zoom range is 0..0x4000. No time-based
        # estimate or invented 20x ratio; scaling is opt-in for compatible cameras.
        self.zoom_available.emit(position is not None)
        if position is not None:
            self._current_zoom_level = max(0, min(1, position / 0x4000))
            self.zoom_level_changed.emit(self._current_zoom_level)

    def _poll_zoom(self):
        if not self._poll_pending:
            self._poll_pending = True
            self._req_poll_zoom.emit()

    def connect(self, config):
        self.stop()
        self.zoom_stop()
        self._connected = False
        self._ptz_generation += 1
        self._zoom_generation += 1
        self._config = config
        self._req_connect.emit(config)

    def disconnect(self):
        self.stop()
        self.zoom_stop()
        self._connected = False
        self._ptz_generation += 1
        self._zoom_generation += 1
        self._zoom_timer.stop()
        self._req_disconnect.emit()

    def shutdown(self):
        if self._shutdown:
            return
        self._shutdown = True
        self._zoom_timer.stop()
        self._ptz_generation += 1
        self._zoom_generation += 1
        if self._worker_thread.isRunning():
            QMetaObject.invokeMethod(self._worker, 'disconnect_camera', Qt.ConnectionType.BlockingQueuedConnection)
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._connected = False

    def move(self, direction, speed=8):
        if self._connected and self._worker.visca_ready:
            self._visca.pan_tilt(speed, speed, direction.value)

    def move_velocity(self, pan, tilt):
        if not self._connected:
            return
        pan = 0.0 if abs(pan) < 0.02 else max(-1, min(1, pan))
        tilt = 0.0 if abs(tilt) < 0.02 else max(-1, min(1, tilt))
        if not pan and not tilt:
            self.stop()
            return
        horizontal = 'Right' if pan > 0 else 'Left' if pan < 0 else ''
        vertical = 'Up' if tilt > 0 else 'Down' if tilt < 0 else ''
        direction = vertical + horizontal
        ps, ts = max(1, round(abs(pan) * 24)), max(1, round(abs(tilt) * 20))
        command = (ps, ts, direction)
        if command == self._last_motion:
            return
        self._ptz_generation += 1  # invalidates delayed stop packets
        self._last_motion = command
        if self._worker.visca_ready:
            self._visca.pan_tilt(ps, ts, direction)
        else:
            self._worker.queue_motion('ptz', (horizontal + vertical, ps, ts))

    def _repeat_stop(self, generation, zoom=False):
        current = self._zoom_generation if zoom else self._ptz_generation
        if self._connected and current == generation and self._worker.visca_ready:
            (self._visca.zoom_stop if zoom else self._visca.stop)()

    def stop(self):
        if not self._connected:
            return
        self._ptz_generation += 1
        generation = self._ptz_generation
        self._last_motion = None
        if self._worker.visca_ready:
            self._visca.stop()
            for delay in (20, 50):
                QTimer.singleShot(delay, lambda g=generation: self._repeat_stop(g))
        else:
            self._worker.queue_motion('ptz', ('Stop', 0, 0))

    def home(self):
        if self._connected and self._worker.visca_ready:
            self._visca.home()

    def _zoom(self, direction, speed):
        if not self._connected:
            return
        command = (direction, max(1, min(7, speed)))
        if self._last_zoom == command:
            return
        self._zoom_generation += 1
        self._last_zoom = command
        if self._worker.visca_ready:
            (self._visca.zoom_tele if direction > 0 else self._visca.zoom_wide)(command[1])
        else:
            self._worker.queue_motion('zoom', ('ZoomIn' if direction > 0 else 'ZoomOut', command[1], 0))

    def zoom_in(self, speed=4):
        self._zoom(1, speed)

    def zoom_out(self, speed=4):
        self._zoom(-1, speed)

    def zoom_stop(self):
        if not self._connected:
            return
        self._zoom_generation += 1
        generation = self._zoom_generation
        self._last_zoom = None
        if self._worker.visca_ready:
            self._visca.zoom_stop()
            QTimer.singleShot(25, lambda g=generation: self._repeat_stop(g, zoom=True))
        else:
            # Native HTTP Stop affects all axes: the app resets the engine too.
            self._worker.queue_motion('zoom', ('Stop', 0, 0))

    def set_image_setting(self, name, value):
        self._req_update_image_param.emit(name, value)

    def apply_all_image_settings(self, settings):
        self._req_apply_all_image.emit(settings)

    def read_image_settings(self):
        self._req_read_image.emit()

    def recall_preset(self, number):
        if self._connected:
            self._req_recall_preset.emit(number)

    def save_preset(self, number, name=''):
        if self._connected:
            self._req_save_preset.emit(number, name)

    def delete_preset(self, number):
        if self._connected:
            self._req_delete_preset.emit(number)

    def export_diagnostic(self, path):
        self._req_diagnostic.emit(path)

    def capture_thumbnail(self, path):
        if self._connected:
            self._req_capture_thumb.emit(path)
        return path
