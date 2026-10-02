import math
from dataclasses import dataclass
from typing import Optional, Any

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QKeyEvent, QFocusEvent, QPolygonF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSlider, QLabel, QGroupBox, QComboBox, QCheckBox, QSizePolicy, QSpinBox
)

from src.core.motion_engine import MotionConfig, EasingCurve

class VirtualJoystick(QWidget):
    """
    Widget de joystick virtual moderno para controle PTZ contínuo.
    Suporta interação tátil por mouse com vetor dinâmico e feedback visual neon.
    """
    velocity_changed = Signal(float, float)  # pan, tilt (-1.0 a 1.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(210, 210)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)

        self.center = QPointF(105.0, 105.0)
        self.radius = 92.0
        self.deadzone_radius = self.radius * 0.15
        self.handle_radius = 18.0

        self.current_pos = QPointF(self.center)
        self.is_dragging = False

        self.pan = 0.0
        self.tilt = 0.0
        self.has_focus = False

    def paintEvent(self, event):
        """Renderiza o joystick estilo gimbal com gradientes e miras concêntricas."""
        from PySide6.QtGui import QRadialGradient, QLinearGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fundo circular com gradiente radial metálico escuro
        bg_grad = QRadialGradient(self.center, self.radius)
        bg_grad.setColorAt(0.0, QColor(36, 42, 53, 230))
        bg_grad.setColorAt(0.7, QColor(22, 26, 33, 240))
        bg_grad.setColorAt(1.0, QColor(14, 17, 22, 255))
        painter.setPen(QPen(QColor(60, 72, 88), 2))
        painter.setBrush(bg_grad)
        painter.drawEllipse(self.center, self.radius, self.radius)

        # Círculos guia concêntricos (33%, 66%)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(70, 84, 104, 70), 1, Qt.PenStyle.DashLine))
        painter.drawEllipse(self.center, self.radius * 0.33, self.radius * 0.33)
        painter.drawEllipse(self.center, self.radius * 0.66, self.radius * 0.66)

        # Linhas de mira (Crosshairs eixos X e Y)
        painter.setPen(QPen(QColor(70, 84, 104, 60), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(self.center.x() - self.radius, self.center.y()),
                         QPointF(self.center.x() + self.radius, self.center.y()))
        painter.drawLine(QPointF(self.center.x(), self.center.y() - self.radius),
                         QPointF(self.center.x(), self.center.y() + self.radius))

        # Zona morta (Deadzone central)
        dz_grad = QRadialGradient(self.center, self.deadzone_radius)
        dz_grad.setColorAt(0.0, QColor(30, 36, 46, 120))
        dz_grad.setColorAt(1.0, QColor(45, 55, 70, 100))
        painter.setPen(QPen(QColor(80, 96, 118, 90), 1))
        painter.setBrush(dz_grad)
        painter.drawEllipse(self.center, self.deadzone_radius, self.deadzone_radius)

        # Vetor de direção e velocidade com cores dinâmicas
        speed = math.hypot(self.pan, self.tilt)
        if speed > 0.02:
            if speed > 0.8:
                vec_color = QColor(255, 61, 0, 220)       # Vermelho elétrico
            elif speed > 0.4:
                vec_color = QColor(255, 179, 0, 220)      # Âmbar/Amarelo
            else:
                vec_color = QColor(0, 229, 255, 220)       # Ciano neon

            # Linha de conexão do centro à manopla
            painter.setPen(QPen(vec_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(self.center, self.current_pos)

        # Ponto central de repouso
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(140, 160, 185, 180))
        painter.drawEllipse(self.center, 3, 3)

        # Manopla do Joystick (Handle com visual 3D chanfrado)
        handle_grad = QRadialGradient(self.current_pos, self.handle_radius)
        if self.is_dragging:
            handle_grad.setColorAt(0.0, QColor(75, 95, 125))
            handle_grad.setColorAt(0.7, QColor(40, 50, 68))
            handle_grad.setColorAt(1.0, QColor(25, 32, 44))
            rim_color = QColor(0, 229, 255, 230)
            glow_dot = QColor(0, 229, 255)
        else:
            handle_grad.setColorAt(0.0, QColor(65, 78, 98))
            handle_grad.setColorAt(0.7, QColor(36, 44, 56))
            handle_grad.setColorAt(1.0, QColor(20, 25, 33))
            rim_color = QColor(90, 108, 132)
            glow_dot = QColor(100, 180, 240)

        # Anel externo da manopla
        painter.setPen(QPen(rim_color, 2))
        painter.setBrush(handle_grad)
        painter.drawEllipse(self.current_pos, self.handle_radius, self.handle_radius)

        # LED central da manopla
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow_dot)
        painter.drawEllipse(self.current_pos, 4, 4)

        # Texto de status da velocidade no rodapé do joystick
        if speed > 0.05:
            painter.setPen(QColor(180, 200, 225, 200))
            font = painter.font()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            pct_text = f"{int(speed * 100)}%"
            painter.drawText(QRectF(0, self.height() - 22, self.width(), 20),
                             Qt.AlignmentFlag.AlignCenter, pct_text)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.update_position(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_dragging:
            self.update_position(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.reset_joystick()

    def update_position(self, pos: QPointF):
        """Atualiza a posição da alavanca e calcula a velocidade."""
        dx = pos.x() - self.center.x()
        dy = pos.y() - self.center.y()
        distance = math.hypot(dx, dy)

        if distance > self.radius:
            dx = dx * self.radius / distance
            dy = dy * self.radius / distance
            distance = self.radius

        self.current_pos = QPointF(self.center.x() + dx, self.center.y() + dy)

        if distance < self.deadzone_radius:
            self.pan = 0.0
            self.tilt = 0.0
        else:
            # Normalizar para -1.0 a 1.0 (invertendo o eixo Y para tilt correto)
            self.pan = dx / self.radius
            self.tilt = -dy / self.radius

        self.velocity_changed.emit(self.pan, self.tilt)
        self.update()

    def reset_joystick(self):
        """Retorna o joystick suavemente para o centro."""
        self.current_pos = QPointF(self.center)
        self.pan = 0.0
        self.tilt = 0.0
        self.velocity_changed.emit(0.0, 0.0)
        self.update()


class DPad(QWidget):
    """
    Directional Pad (D-Pad) profissional com 8 direções e botão STOP centralizado.
    """
    direction_pressed = Signal(float, float) # pan, tilt
    direction_released = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mapa de botões: (linha, coluna): (ícone, pan, tilt, tooltip, is_cardinal)
        buttons_map = {
            (0, 0): ("↖", -1.0, 1.0, "Noroeste (Cima + Esquerda)", False),
            (0, 1): ("▲", 0.0, 1.0, "Cima (Tilt Up)", True),
            (0, 2): ("↗", 1.0, 1.0, "Nordeste (Cima + Direita)", False),
            (1, 0): ("◀", -1.0, 0.0, "Esquerda (Pan Left)", True),
            (1, 1): ("⏹", 0.0, 0.0, "Parar Movimento (Stop)", None),
            (1, 2): ("▶", 1.0, 0.0, "Direita (Pan Right)", True),
            (2, 0): ("↙", -1.0, -1.0, "Sudoeste (Baixo + Esquerda)", False),
            (2, 1): ("▼", 0.0, -1.0, "Baixo (Tilt Down)", True),
            (2, 2): ("↘", 1.0, -1.0, "Sudeste (Baixo + Direita)", False),
        }

        self.buttons = {}

        for pos, (icon, pan, tilt, tip, is_cardinal) in buttons_map.items():
            btn = QPushButton(icon)
            btn.setFixedSize(48, 48)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setToolTip(tip)

            if pos == (1, 1):
                # Botão STOP centralizado com destaque em vermelho escuro
                btn.clicked.connect(self.direction_released.emit)
            else:
                # Botões direcionais com estilo moderno
                bg_col = "#2a323f" if is_cardinal else "#212732"
                txt_col = "#ffffff" if is_cardinal else "#90caf9"
                font_sz = "16px" if is_cardinal else "14px"
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg_col};
                        color: {txt_col};
                        border: 1px solid #3d495c;
                        border-radius: 8px;
                        font-size: {font_sz};
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: #384558;
                        border-color: #4fc3f7;
                        color: #4fc3f7;
                    }}
                    QPushButton:pressed {{
                        background-color: #0288d1;
                        border-color: #4fc3f7;
                        color: #ffffff;
                    }}
                """)
                btn.pressed.connect(lambda p=pan, t=tilt: self.direction_pressed.emit(p, t))
                btn.released.connect(self.direction_released.emit)

            layout.addWidget(btn, pos[0], pos[1])
            self.buttons[pos] = btn


class PTZControlPanel(QWidget):
    max_speed_changed = Signal(int)
    config_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        group = QGroupBox("Enquadramento")
        gl = QVBoxLayout(group)
        self.input_combo = QComboBox()
        self.input_combo.addItems(["Joystick virtual", "Setas na tela", "Controle USB / Bluetooth"])
        gl.addWidget(self.input_combo)
        self.joystick = VirtualJoystick()
        self.dpad = DPad()
        gl.addWidget(self.joystick, alignment=Qt.AlignmentFlag.AlignHCenter)
        gl.addWidget(self.dpad, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.gamepad_options = QWidget()
        gamepad_layout = QVBoxLayout(self.gamepad_options)
        self.gamepad_status = QLabel("Conecte um controle USB ou Bluetooth.")
        self.gamepad_status.setWordWrap(True)
        gamepad_layout.addWidget(self.gamepad_status)
        self.gamepad_axes = []
        for label, default in [("Eixo horizontal", 0), ("Eixo vertical", 1), ("Eixo de zoom", 3)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            box = QSpinBox()
            box.setRange(0, 15)
            box.setValue(default)
            self.gamepad_axes.append(box)
            row.addWidget(box)
            gamepad_layout.addLayout(row)
        note = QLabel("Botão 0: parada de emergência.\nApós parar, centralize os eixos para retomar.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        gamepad_layout.addWidget(note)
        gl.addWidget(self.gamepad_options)
        self.gamepad_options.hide()
        self.dpad.setVisible(False)
        self.input_combo.currentIndexChanged.connect(self._change_input)
        self.joystick.velocity_changed.connect(self._on_joystick_velocity)
        self.dpad.direction_pressed.connect(self._on_dpad_pressed)
        self.dpad.direction_released.connect(self._on_dpad_released)
        hint = QLabel("Segure para mover · solte para desacelerar")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gl.addWidget(hint)
        layout.addWidget(group)
        group = QGroupBox("Zoom")
        gl = QVBoxLayout(group)
        row = QHBoxLayout()
        self.zoom_out_btn = QPushButton("−  Afastar")
        self.zoom_in_btn = QPushButton("+  Aproximar")
        for button, value in [(self.zoom_out_btn, -1), (self.zoom_in_btn, 1)]:
            button.pressed.connect(lambda v=value: self.engine.set_target_zoom(v) if self.engine else None)
            button.released.connect(self._on_zoom_released)
            row.addWidget(button)
        gl.addLayout(row)
        self.zoom_val_lbl = QLabel("Posição indisponível")
        self.zoom_val_lbl.setObjectName("muted")
        gl.addWidget(self.zoom_val_lbl)
        layout.addWidget(group)
        group = QGroupBox("Velocidade")
        gl = QVBoxLayout(group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Limite de movimento"))
        row.addStretch()
        self.speed_val_lbl = QLabel("8 / 24")
        row.addWidget(self.speed_val_lbl)
        gl.addLayout(row)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 24)
        self.speed_slider.setValue(8)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        gl.addWidget(self.speed_slider)
        layout.addWidget(group)
        advanced = QPushButton("Suavidade e compensação de zoom")
        advanced.setCheckable(True)
        layout.addWidget(advanced)
        group = QGroupBox("Ajustes de movimento")
        gl = QVBoxLayout(group)
        self.accel_slider = QSlider(Qt.Orientation.Horizontal)
        self.accel_slider.setRange(50, 1500)
        self.accel_slider.setValue(300)
        self.decel_slider = QSlider(Qt.Orientation.Horizontal)
        self.decel_slider.setRange(50, 1000)
        self.decel_slider.setValue(200)
        for label, slider in [("Tempo de aceleração", self.accel_slider), ("Tempo de desaceleração", self.decel_slider)]:
            gl.addWidget(QLabel(label))
            gl.addWidget(slider)
            slider.valueChanged.connect(self._update_config)
        self.curve_combo = QComboBox()
        self.curve_combo.addItems(["Linear", "Suave", "Muito suave"])
        self.curve_combo.setCurrentIndex(1)
        self.curve_combo.currentIndexChanged.connect(self._update_config)
        gl.addWidget(self.curve_combo)
        self.auto_scale_cb = QCheckBox("Reduzir velocidade ao aproximar")
        self.auto_scale_cb.setToolTip("Opcional. Exige leitura VISCA de zoom e faixa óptica compatível (0 a 0x4000).")
        self.auto_scale_cb.toggled.connect(self._update_config)
        gl.addWidget(self.auto_scale_cb)
        layout.addWidget(group)
        group.setVisible(False)
        advanced.toggled.connect(group.setVisible)

    def _change_input(self, index):
        self.joystick.reset_joystick()
        if self.engine:
            self.engine.emergency_stop()
        self.joystick.setVisible(index == 0)
        self.dpad.setVisible(index == 1)
        self.gamepad_options.setVisible(index == 2)
        self.zoom_in_btn.setEnabled(index != 2)
        self.zoom_out_btn.setEnabled(index != 2)

    def set_motion_engine(self, engine):
        self.engine = engine
        self._update_config()

    def set_zoom_available(self, available):
        self.auto_scale_cb.setEnabled(available)
        if not available:
            self.auto_scale_cb.setChecked(False)
            self.zoom_val_lbl.setText("Posição indisponível")

    def set_current_zoom_level(self, level):
        self.zoom_val_lbl.setText(f"Posição VISCA: {round(level * 100)}%")

    def _on_speed_changed(self, value):
        self.speed_val_lbl.setText(f"{value} / 24")
        self.max_speed_changed.emit(value)
        self._update_config()

    def _on_dpad_pressed(self, pan, tilt):
        if self.engine:
            self.engine.set_target_velocity(pan, tilt)

    def _on_dpad_released(self):
        if self.engine:
            self.engine.set_target_velocity(0, 0)

    def _on_joystick_velocity(self, pan, tilt):
        if self.engine:
            if not pan and not tilt:
                self.engine.set_target_velocity(0, 0)
            else:
                self.engine.set_mouse_velocity(pan, tilt)

    def _on_zoom_released(self):
        if self.engine:
            self.engine.set_target_zoom(0)

    def _update_config(self, *args):
        config = MotionConfig(accel_time_ms=self.accel_slider.value(), decel_time_ms=self.decel_slider.value(),
            easing_curve=[EasingCurve.LINEAR, EasingCurve.EASE_IN_OUT, EasingCurve.SMOOTH_STEP][self.curve_combo.currentIndex()],
            zoom_speed_scaling=self.auto_scale_cb.isChecked(), max_ptz_speed=self.speed_slider.value() / 24)
        self.config_changed.emit(config)
        if self.engine:
            self.engine.set_config(config)
