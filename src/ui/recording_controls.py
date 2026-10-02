from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


class RecordingControls(QWidget):
    recording_toggled = Signal(bool)
    snapshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_recording = False
        self.elapsed_time = 0
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.btn_record = QPushButton('●  Gravar vídeo')
        self.btn_snapshot = QPushButton('Capturar imagem')
        self.lbl_timer = QLabel('')
        self.lbl_timer.setObjectName('muted')
        self.btn_record.clicked.connect(lambda: self.recording_toggled.emit(not self.is_recording))
        self.btn_snapshot.clicked.connect(self.snapshot_requested)
        row.addWidget(self.btn_record)
        row.addWidget(self.btn_snapshot)
        row.addWidget(self.lbl_timer)
        row.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_timer_display)

    def set_recording(self, active):
        self.is_recording = active
        self.btn_record.setText('■  Finalizar gravação' if active else '●  Gravar vídeo')
        if active:
            self.elapsed_time = 0
            self.timer.start()
        else:
            self.timer.stop()
            self.lbl_timer.clear()

    def _update_timer_display(self):
        self.elapsed_time += 1
        self.lbl_timer.setText(f'REC {self.elapsed_time // 60:02d}:{self.elapsed_time % 60:02d}')
