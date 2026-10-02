from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox
)

class FocusControlPanel(QWidget):
    """
    Painel de controle de foco para a câmera PTZ.
    Suporta foco automático e manual com botões Near/Far e One Push.
    """
    focus_mode_changed = Signal(str)  # 'auto' ou 'manual'
    focus_near_start = Signal()
    focus_far_start = Signal()
    focus_stop = Signal()
    focus_one_push = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = 'auto'
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Foco")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 14)
        layout.setSpacing(10)

        # Modo de Foco
        mode_layout = QHBoxLayout()
        self.mode_label = QLabel("Automático")
        self.mode_label.setStyleSheet("font-weight: 600; color: #4fc3f7;")
        self.toggle_mode_btn = QPushButton("Usar manual")
        self.toggle_mode_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle_mode_btn.setToolTip("Alternar modo de foco (F)")
        self.toggle_mode_btn.clicked.connect(self._on_toggle_mode)

        mode_layout.addWidget(self.mode_label)
        mode_layout.addStretch()
        mode_layout.addWidget(self.toggle_mode_btn)
        layout.addLayout(mode_layout)

        # Controles Manuais
        controls_layout = QHBoxLayout()

        self.near_btn = QPushButton("Perto")
        self.near_btn.setFixedHeight(36)
        self.near_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.near_btn.setToolTip("Ajustar foco próximo (Tecla [)")
        self.near_btn.pressed.connect(self.focus_near_start.emit)
        self.near_btn.released.connect(self.focus_stop.emit)

        self.far_btn = QPushButton("Longe")
        self.far_btn.setFixedHeight(36)
        self.far_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.far_btn.setToolTip("Ajustar foco distante (Tecla ])")
        self.far_btn.pressed.connect(self.focus_far_start.emit)
        self.far_btn.released.connect(self.focus_stop.emit)

        controls_layout.addWidget(self.near_btn)
        controls_layout.addWidget(self.far_btn)
        layout.addLayout(controls_layout)

        self.one_push_btn = QPushButton("Focar uma vez")
        self.one_push_btn.setFixedHeight(36)
        self.one_push_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.one_push_btn.setToolTip("Executa auto-foco rápido imediato uma vez")
        self.one_push_btn.clicked.connect(self.focus_one_push.emit)
        layout.addWidget(self.one_push_btn)

        main_layout.addWidget(group)
        self._update_ui_state()

    def _on_toggle_mode(self):
        """Alterna entre os modos de foco automático e manual."""
        if self.current_mode == 'auto':
            self.current_mode = 'manual'
        else:
            self.current_mode = 'auto'

        self.focus_mode_changed.emit(self.current_mode)
        self._update_ui_state()

    def _update_ui_state(self):
        """Atualiza a visibilidade e habilitação dos controles baseando-se no modo atual."""
        is_manual = (self.current_mode == 'manual')

        self.near_btn.setEnabled(is_manual)
        self.far_btn.setEnabled(is_manual)
        self.one_push_btn.setVisible(is_manual)

        if is_manual:
            self.mode_label.setText("Manual")
            self.toggle_mode_btn.setText("Usar automático")
        else:
            self.mode_label.setText("Automático")
            self.toggle_mode_btn.setText("Usar manual")
