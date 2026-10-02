import logging
from dataclasses import dataclass
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QSpinBox, QLabel, QMessageBox,
    QDoubleSpinBox
)

logger = logging.getLogger(__name__)

@dataclass
class TourStep:
    """Passo de uma patrulha (tour)."""
    preset_number: int
    dwell_time_seconds: float = 5.0
    transition_speed: int = 8

    # Mocking a preset name property for UI visualization
    preset_name: str = "Preset"


class TourManager(QObject):
    """
    Gerenciador de patrulha/tour para ciclagem automática de presets.
    """
    tour_started = Signal()
    tour_stopped = Signal()
    tour_step_changed = Signal(int, int)  # current_step, total_steps
    goto_preset = Signal(int)             # preset number to recall

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._steps: List[TourStep] = []
        self._is_running: bool = False
        self._current_step_index: int = 0
        self._loop_count: int = 0
        self._current_loop: int = 0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next_step)

    def add_step(self, step: TourStep):
        """Adiciona um novo passo ao tour."""
        self._steps.append(step)

    def remove_step(self, index: int):
        """Remove o passo especificado."""
        if 0 <= index < len(self._steps):
            self._steps.pop(index)
            if self._is_running and index <= self._current_step_index:
                self._current_step_index = max(0, self._current_step_index - 1)

    def move_step(self, from_index: int, to_index: int):
        """Move um passo de uma posição para outra."""
        if 0 <= from_index < len(self._steps) and 0 <= to_index < len(self._steps):
            step = self._steps.pop(from_index)
            self._steps.insert(to_index, step)

    def start(self, loop_count: int = 0):
        """Inicia a patrulha."""
        if not self._steps:
            return

        self._is_running = True
        self._loop_count = loop_count
        self._current_loop = 0
        self._current_step_index = 0
        self.tour_started.emit()
        self._execute_current_step()

    def pause(self):
        """Pausa a patrulha mantendo a posição."""
        self._is_running = False
        self._timer.stop()
        self.tour_stopped.emit()

    def stop(self):
        """Interrompe a patrulha e zera a posição."""
        self._is_running = False
        self._timer.stop()
        self._current_step_index = 0
        self.tour_stopped.emit()

    def is_running(self) -> bool:
        """Verifica se a patrulha está em execução."""
        return self._is_running

    def _execute_current_step(self):
        if not self._is_running or not self._steps:
            return

        step = self._steps[self._current_step_index]
        self.tour_step_changed.emit(self._current_step_index + 1, len(self._steps))

        # Chama o preset
        self.goto_preset.emit(step.preset_number)

        # Agenda o próximo passo baseado no dwell_time
        self._timer.start(int(step.dwell_time_seconds * 1000))

    def _next_step(self):
        if not self._is_running:
            return

        self._current_step_index += 1

        if self._current_step_index >= len(self._steps):
            self._current_loop += 1
            if self._loop_count != 0 and self._current_loop >= self._loop_count:
                # Fim dos ciclos
                self.stop()
                return
            self._current_step_index = 0

        self._execute_current_step()


class TourManagerPanel(QWidget):
    """
    Interface de usuário para o TourManager.
    """
    def __init__(self, tour_manager: TourManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = tour_manager
        self.manager.tour_step_changed.connect(self._update_status)
        self.manager.tour_started.connect(self._on_started)
        self.manager.tour_stopped.connect(self._on_stopped)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Lista de passos
        self.list_widget = QListWidget()
        layout.addWidget(QLabel("Passos da Patrulha:"))
        layout.addWidget(self.list_widget)

        # Botões de lista
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar")
        self.btn_remove = QPushButton("Remover")
        self.btn_up = QPushButton("Sobe")
        self.btn_down = QPushButton("Desce")

        self.btn_add.clicked.connect(self._add_step)
        self.btn_remove.clicked.connect(self._remove_step)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)

        for btn in (self.btn_add, self.btn_remove, self.btn_up, self.btn_down):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # Configurações globais de execução
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Ciclos (0=Infinito):"))
        self.spin_loops = QSpinBox()
        self.spin_loops.setRange(0, 999)
        self.spin_loops.setValue(0)
        config_layout.addWidget(self.spin_loops)

        config_layout.addStretch()
        layout.addLayout(config_layout)

        # Status Label
        self.lbl_status = QLabel("Status: Parado")
        self.lbl_status.setStyleSheet("font-weight: bold; color: gray;")
        layout.addWidget(self.lbl_status)

        # Controles
        ctrl_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_stop = QPushButton("⏹ Parar")

        self.btn_start.clicked.connect(self._start_tour)
        self.btn_pause.clicked.connect(self.manager.pause)
        self.btn_stop.clicked.connect(self.manager.stop)

        for btn in (self.btn_start, self.btn_pause, self.btn_stop):
            ctrl_layout.addWidget(btn)
        layout.addLayout(ctrl_layout)

        self._update_ui_state()

    def _add_step(self):
        # Exemplo simplificado. Na prática abriria um diálogo para escolher o preset e os parâmetros.
        step = TourStep(preset_number=1, dwell_time_seconds=5.0, transition_speed=8, preset_name="Preset 1")
        self.manager.add_step(step)
        self._refresh_list()

    def _remove_step(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.manager.remove_step(row)
            self._refresh_list()

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            self.manager.move_step(row, row - 1)
            self._refresh_list()
            self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row >= 0 and row < self.list_widget.count() - 1:
            self.manager.move_step(row, row + 1)
            self._refresh_list()
            self.list_widget.setCurrentRow(row + 1)

    def _refresh_list(self):
        self.list_widget.clear()
        for step in self.manager._steps:
            text = f"Preset '{step.preset_name}' (Nº {step.preset_number}) - Tempo: {step.dwell_time_seconds}s - Vel: {step.transition_speed}"
            self.list_widget.addItem(text)

    def _start_tour(self):
        if not self.manager._steps:
            QMessageBox.warning(self, "Atenção", "Adicione passos antes de iniciar.")
            return
        self.manager.start(self.spin_loops.value())

    def _update_status(self, current: int, total: int):
        if self.manager._steps:
            step = self.manager._steps[current - 1]
            self.lbl_status.setText(f"Passo {current}/{total} - Preset '{step.preset_name}' - Aguardando {step.dwell_time_seconds}s")
            self.lbl_status.setStyleSheet("font-weight: bold; color: green;")

    def _on_started(self):
        self._update_ui_state()

    def _on_stopped(self):
        self.lbl_status.setText("Status: Parado")
        self.lbl_status.setStyleSheet("font-weight: bold; color: gray;")
        self._update_ui_state()

    def _update_ui_state(self):
        running = self.manager.is_running()
        self.btn_add.setEnabled(not running)
        self.btn_remove.setEnabled(not running)
        self.btn_up.setEnabled(not running)
        self.btn_down.setEnabled(not running)
        self.btn_start.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running)
