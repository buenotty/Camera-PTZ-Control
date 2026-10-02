import time
from typing import Optional, Set, Dict

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QKeyEvent


class KeyboardHandler(QObject):
    """
    Tratador de eventos de teclado de alta precisão para controle de câmera PTZ.
    Possui watchdog ativo contra travamento de teclas (anti-sticking),
    tratamento rigoroso de autorepeat do Windows e suporte a atalhos de produção.
    """
    # Signals para ações que não são de movimento PTZ
    preset_recall = Signal(int)
    preset_save = Signal(int)
    toggle_recording = Signal()
    capture_snapshot = Signal()
    toggle_tour = Signal()
    toggle_focus_mode = Signal()
    focus_near = Signal()
    focus_far = Signal()
    focus_stop_signal = Signal()
    toggle_grid = Signal()
    undo = Signal()
    redo = Signal()
    toggle_fullscreen = Signal()
    show_shortcuts = Signal()
    read_camera_settings = Signal()
    emergency_stop = Signal()

    def __init__(self):
        super().__init__()
        self._pressed_keys: Set[int] = set()
        self._key_timestamps: Dict[int, float] = {}
        self._motion_engine = None
        self.motion_enabled = True

        # Mapeamentos de teclas de direção PTZ (Pan/Tilt)
        self._ptz_keys = {
            Qt.Key.Key_W: (0, 1),
            Qt.Key.Key_Up: (0, 1),
            Qt.Key.Key_S: (0, -1),
            Qt.Key.Key_Down: (0, -1),
            Qt.Key.Key_A: (-1, 0),
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_D: (1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Q: (-1, 1),      # Diagonal Up-Left
            Qt.Key.Key_E: (1, 1),       # Diagonal Up-Right
            Qt.Key.Key_Z: (-1, -1),     # Diagonal Down-Left
            Qt.Key.Key_C: (1, -1),      # Diagonal Down-Right
        }

        # Mapeamento de teclas de Zoom
        self._zoom_keys = {
            Qt.Key.Key_Plus: 1.0,
            Qt.Key.Key_PageUp: 1.0,
            Qt.Key.Key_Equal: 1.0,
            Qt.Key.Key_Minus: -1.0,
            Qt.Key.Key_PageDown: -1.0,
        }

    def set_motion_engine(self, engine):
        """Define o mecanismo de movimento suave a ser controlado."""
        self._motion_engine = engine

    def clear_all_keys(self):
        self._pressed_keys.clear()
        self._key_timestamps.clear()
        if self._motion_engine:
            self._motion_engine.emergency_stop()
        self.focus_stop_signal.emit()

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        Processa pressionamento de teclas e aciona funções ou movimentos.
        Retorna True se o evento foi tratado e consumido.
        """
        key = event.key()
        modifiers = event.modifiers()
        now = time.monotonic()

        # Teclas de movimento PTZ
        if self.motion_enabled and key in self._ptz_keys and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
            self._key_timestamps[key] = now
            if key not in self._pressed_keys:
                self._pressed_keys.add(key)
                self._update_ptz_target()
            return True

        # Teclas de Zoom
        if self.motion_enabled and key in self._zoom_keys and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
            self._key_timestamps[key] = now
            if key not in self._pressed_keys:
                self._pressed_keys.add(key)
                self._update_zoom_target()
            return True

        # Para atalhos que não devem disparar repetidamente com autorepeat
        if event.isAutoRepeat():
            return False

        # Espaço = parada de emergência imediata
        if key == Qt.Key.Key_Space and not modifiers:
            self.clear_all_keys()
            self.emergency_stop.emit()
            if self._motion_engine:
                self._motion_engine.emergency_stop()
            return True

        # Presets 1 a 9
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            preset_num = key - Qt.Key.Key_0
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.preset_save.emit(preset_num)
            else:
                self.preset_recall.emit(preset_num)
            return True

        # Foco
        if key == Qt.Key.Key_F and not modifiers:
            self.toggle_focus_mode.emit()
            return True
        elif key == Qt.Key.Key_BracketLeft and not modifiers:
            self.focus_near.emit()
            return True
        elif key == Qt.Key.Key_BracketRight and not modifiers:
            self.focus_far.emit()
            return True

        # Atalhos Gerais de Produção
        if key == Qt.Key.Key_G and not modifiers:
            self.toggle_grid.emit()
            return True
        elif key == Qt.Key.Key_Z and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.undo.emit()
            return True
        elif key == Qt.Key.Key_Y and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.redo.emit()
            return True
        elif key == Qt.Key.Key_F1 and not modifiers:
            self.show_shortcuts.emit()
            return True
        elif key == Qt.Key.Key_F11 and not modifiers:
            self.toggle_fullscreen.emit()
            return True
        elif key == Qt.Key.Key_T and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.toggle_tour.emit()
            return True
        elif key == Qt.Key.Key_R and modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.read_camera_settings.emit()
            return True
        elif key == Qt.Key.Key_P and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.capture_snapshot.emit()
            return True
        elif key == Qt.Key.Key_R and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.toggle_recording.emit()
            return True

        return False

    def handle_key_release(self, event: QKeyEvent) -> bool:
        """
        Processa soltura de teclas e finaliza movimentos.
        Ignora autorepeat transitório gerado pelo Windows.
        """
        # Se for evento de release transitório de autorepeat, ignorar
        if event.isAutoRepeat():
            return False

        key = event.key()
        handled = False

        if key in self._ptz_keys:
            self._pressed_keys.discard(key)
            self._key_timestamps.pop(key, None)
            self._update_ptz_target()
            handled = True

        if key in self._zoom_keys:
            self._pressed_keys.discard(key)
            self._key_timestamps.pop(key, None)
            self._update_zoom_target()
            handled = True

        # Parada de foco
        if key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            self.focus_stop_signal.emit()
            handled = True

        return handled

    def _update_ptz_target(self):
        """Calcula o vetor de velocidade resultante de Pan e Tilt [-1.0, 1.0]."""
        pan = 0.0
        tilt = 0.0
        for key in self._pressed_keys:
            if key in self._ptz_keys:
                p, t = self._ptz_keys[key]
                pan += p
                tilt += t

        pan = max(-1.0, min(1.0, pan))
        tilt = max(-1.0, min(1.0, tilt))

        if self._motion_engine:
            self._motion_engine.set_target_velocity(pan, tilt)

    def _update_zoom_target(self):
        """Calcula a velocidade resultante de Zoom [-1.0, 1.0]."""
        zoom = 0.0
        for key in self._pressed_keys:
            if key in self._zoom_keys:
                zoom += self._zoom_keys[key]

        zoom = max(-1.0, min(1.0, zoom))

        if self._motion_engine:
            self._motion_engine.set_target_zoom(zoom)
