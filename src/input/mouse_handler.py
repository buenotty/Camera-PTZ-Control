from PySide6.QtCore import QObject, Signal, QPointF, QTimer
import math

class MouseHandler(QObject):
    """
    Processa eventos de mouse do VideoPanel e converte em comandos PTZ via MotionEngine.
    Permite arrastar para mover e rolar a roda do mouse para aplicar zoom.
    """

    zoom_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self._motion_engine = None
        self._is_dragging = False
        self._drag_origin = QPointF(0, 0)
        self._viewport_size = (1280, 720)
        self._deadzone_px = 15

        # Timer para parar o zoom automaticamente após a rolagem do mouse
        self._zoom_stop_timer = QTimer(self)
        self._zoom_stop_timer.setSingleShot(True)
        self._zoom_stop_timer.setInterval(300)
        self._zoom_stop_timer.timeout.connect(self._stop_zoom)

    def set_motion_engine(self, engine):
        """Define o mecanismo de movimento a ser controlado."""
        self._motion_engine = engine

    def set_viewport_size(self, width: int, height: int):
        """Atualiza as dimensões da área de visualização para normalização correta."""
        self._viewport_size = (width, height)

    def on_drag_started(self, x: int, y: int):
        """Inicia o movimento por arrasto do mouse (click principal)."""
        self._is_dragging = True
        self._drag_origin = QPointF(x, y)

    def on_drag_moved(self, x: int, y: int):
        """Calcula e aplica movimento PTZ contínuo com base na distância de arrasto."""
        if not self._is_dragging:
            return

        dx = x - self._drag_origin.x()
        dy = y - self._drag_origin.y()

        distance = math.sqrt(dx * dx + dy * dy)

        if distance < self._deadzone_px:
            if self._motion_engine:
                self._motion_engine.set_target_velocity(0.0, 0.0)
            return

        max_distance = min(self._viewport_size[0], self._viewport_size[1]) / 3
        pan_norm = max(-1.0, min(1.0, dx / max_distance))
        tilt_norm = max(-1.0, min(1.0, -dy / max_distance)) # Y invertido

        if self._motion_engine:
            self._motion_engine.set_mouse_velocity(pan_norm, tilt_norm)

    def on_drag_ended(self):
        """Finaliza o movimento por arrasto (soltura do click)."""
        self._is_dragging = False
        if self._motion_engine:
            self._motion_engine.set_target_velocity(0.0, 0.0)

    def on_scroll(self, delta: int):
        """Aplica zoom baseado na rolagem da roda do mouse."""
        zoom_vel = 0.5 if delta > 0 else -0.5
        if self._motion_engine:
            self._motion_engine.set_target_zoom(zoom_vel)
            self._zoom_stop_timer.start()

    def _stop_zoom(self):
        """Interrompe o zoom, chamado internamente pelo QTimer."""
        if self._motion_engine:
            self._motion_engine.set_target_zoom(0.0)
