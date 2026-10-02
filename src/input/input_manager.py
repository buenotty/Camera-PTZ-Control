from PySide6.QtCore import QObject, Signal

# Dummy enum for type-hinting if it's not defined yet, otherwise comment this out
# from src.core.models import InputMode
from enum import Enum
class InputMode(Enum):
    KEYBOARD = 1
    MOUSE = 2
    HYBRID = 3

class InputManager(QObject):
    """
    Gerenciador central de entradas que coordena o teclado e o mouse.
    Permite alternar entre os modos de controle e roteia os eventos.
    """
    mode_changed = Signal(InputMode)

    def __init__(self):
        super().__init__()
        self._mode = InputMode.HYBRID
        self._keyboard_handler = None
        self._mouse_handler = None

    @property
    def mode(self) -> InputMode:
        """Obtém o modo de entrada atual."""
        return self._mode

    def set_mode(self, mode: InputMode):
        """Define o modo de entrada atual e emite o sinal mode_changed."""
        if self._mode != mode:
            self._mode = mode
            self.mode_changed.emit(self._mode)

    def register_keyboard_handler(self, handler):
        """Registra o tratador de eventos de teclado."""
        self._keyboard_handler = handler

    def register_mouse_handler(self, handler):
        """Registra o tratador de eventos de mouse."""
        self._mouse_handler = handler

    def notify_keyboard_input(self):
        """Notifica o uso do teclado. Pode alterar o modo automaticamente."""
        if self._mode == InputMode.HYBRID:
            return
        if self._mode == InputMode.MOUSE:
            self.set_mode(InputMode.HYBRID)

    def notify_mouse_input(self):
        """Notifica o uso do mouse. Pode alterar o modo automaticamente."""
        if self._mode == InputMode.HYBRID:
            return
        if self._mode == InputMode.KEYBOARD:
            self.set_mode(InputMode.HYBRID)

    def get_key_bindings(self) -> dict:
        """Obtém os atalhos de teclado atuais."""
        if self._keyboard_handler:
            return {
                'ptz': self._keyboard_handler._ptz_keys,
                'zoom': self._keyboard_handler._zoom_keys
            }
        return {}

    def set_key_bindings(self, bindings: dict):
        """Atualiza os atalhos de teclado atuais."""
        if self._keyboard_handler:
            if 'ptz' in bindings:
                self._keyboard_handler._ptz_keys = bindings['ptz']
            if 'zoom' in bindings:
                self._keyboard_handler._zoom_keys = bindings['zoom']
