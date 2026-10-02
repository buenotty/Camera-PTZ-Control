"""Optional USB/Bluetooth controller support, with neutral-before-rearm."""
import math
from PySide6.QtCore import QObject, QTimer, Signal


class GamepadHandler(QObject):
    status_changed = Signal(str)

    def __init__(self, engine, active=lambda: True, backend=None):
        super().__init__()
        self.engine, self.active, self.backend = engine, active, backend
        self.axes = (0, 1, 3)
        self.joystick = None
        self.enabled = False
        self.armed = False
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.poll)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.suspend()
        self.engine.emergency_stop()
        if enabled:
            if self.backend is None:
                try:
                    import pygame
                    self.backend = pygame
                    pygame.display.init()
                    pygame.joystick.init()
                except (ImportError, RuntimeError):
                    self.status_changed.emit('Instale requirements-gamepad.txt para usar um controle físico.')
                    self.enabled = False
                    return
            self.timer.start()
        else:
            self.timer.stop()

    def suspend(self):
        self.armed = False

    @staticmethod
    def normalized(value):
        value = max(-1.0, min(1.0, value))
        if abs(value) < 0.15:
            return 0.0
        return math.copysign(((abs(value) - 0.15) / 0.85) ** 1.5, value)

    def poll(self):
        if not self.enabled:
            return
        if not self.active():
            if self.armed:
                self.engine.emergency_stop()
            self.suspend()
            return
        try:
            self.backend.event.pump()
            if self.backend.joystick.get_count() == 0:
                if self.joystick is not None:
                    self.engine.emergency_stop()
                self.joystick = None
                self.suspend()
                self.status_changed.emit('Conecte um controle USB ou Bluetooth.')
                return
            if self.joystick is None:
                self.joystick = self.backend.joystick.Joystick(0)
                self.joystick.init()
                self.status_changed.emit(self.joystick.get_name() + ' · centralize os eixos para iniciar')
            if max(self.axes) >= self.joystick.get_numaxes():
                self.engine.emergency_stop()
                self.suspend()
                self.status_changed.emit('Escolha eixos disponíveis neste controle.')
                return
            pan, tilt, zoom = [self.normalized(self.joystick.get_axis(axis)) for axis in self.axes]
            emergency = self.joystick.get_numbuttons() > 0 and self.joystick.get_button(0)
            if emergency:
                self.engine.emergency_stop()
                self.suspend()
                self.status_changed.emit('Parado · solte o botão e centralize os eixos')
                return
            if not self.armed:
                if not any((pan, tilt, zoom)):
                    self.armed = True
                    self.status_changed.emit(self.joystick.get_name() + ' · pronto')
                return
            self.engine.set_target_velocity(pan, -tilt)
            self.engine.set_target_zoom(-zoom)
        except Exception:
            self.engine.emergency_stop()
            self.joystick = None
            self.suspend()
            self.status_changed.emit('Controle indisponível. Verifique a conexão.')

    def shutdown(self):
        self.timer.stop()
        self.enabled = False
        if self.joystick:
            self.joystick.quit()
            self.joystick = None
