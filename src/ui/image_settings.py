"""Edit a draft, then apply supported image fields with camera confirmation."""
import copy
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QScrollArea, QSpinBox, QComboBox, QCheckBox, QPushButton)
from src.core.models import ImageSettings, ExposureMode, WhiteBalanceMode
from src.utils.history import SettingsHistory


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class _NumericSettingRow(QWidget):
    value_changed = Signal(int)

    def __init__(self, label, min_val, max_val, default_val, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        self.lbl = QLabel(label)
        self.spin = NoWheelSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(default_val)
        self.spin.setFixedWidth(90)
        self.spin.valueChanged.connect(self.value_changed)
        row.addWidget(self.lbl)
        row.addStretch()
        row.addWidget(self.spin)

    def value(self):
        return self.spin.value()

    def set_value(self, value):
        self.spin.setValue(value)

    def block_signals(self, block):
        self.spin.blockSignals(block)

    def set_enabled(self, enabled):
        self.setEnabled(enabled)


class ImageSettingsPanel(QWidget):
    setting_changed = Signal(str, object)
    apply_all_requested = Signal(object)
    read_from_camera = Signal()

    ROWS = {
        'brightness': ('Brilho', 0, 100, 'row_brightness'),
        'contrast': ('Contraste', 0, 100, 'row_contrast'),
        'saturation': ('Saturação', 0, 100, 'row_saturation'),
        'hue': ('Matiz', 0, 100, 'row_hue'),
        'sharpness': ('Nitidez', 0, 100, 'row_sharpness'),
        'iris': ('Abertura', 0, 17, 'row_iris'),
        'gain': ('Ganho', 0, 15, 'row_gain'),
        'shutter_speed': ('Obturador', 0, 21, 'row_shutter'),
        'exposure_compensation_value': ('Compensação de exposição', -10, 10, 'row_exp_comp'),
        'red_gain': ('Ganho vermelho', 0, 255, 'row_red_gain'),
        'blue_gain': ('Ganho azul', 0, 255, 'row_blue_gain'),
        'noise_reduction': ('Redução de ruído', 0, 100, 'row_noise_reduction'),
    }
    EXPOSURE = [ExposureMode.AUTO, ExposureMode.MANUAL, ExposureMode.IRIS_PRIORITY, ExposureMode.SHUTTER_PRIORITY]
    WHITE_BALANCE = [WhiteBalanceMode.AUTO, WhiteBalanceMode.INDOOR, WhiteBalanceMode.OUTDOOR, WhiteBalanceMode.MANUAL, WhiteBalanceMode.ONE_PUSH]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_settings = ImageSettings()
        self._baseline = copy.deepcopy(self._current_settings)
        self._settings_history = SettingsHistory()
        self._settings_history.push(copy.deepcopy(self._current_settings))
        self._updating = False
        self._support = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.status = QLabel('Conecte uma câmera para ler os ajustes disponíveis.')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.btn_read = QPushButton('Ler câmera')
        self.btn_apply = QPushButton('Aplicar ajustes')
        self.btn_apply.setObjectName('primaryButton')
        self.btn_read.clicked.connect(self.read_from_camera)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        row.addWidget(self.btn_read)
        row.addWidget(self.btn_apply)
        layout.addLayout(row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        gl = QVBoxLayout(content)
        gl.setContentsMargins(0, 0, 0, 0)
        groups = [('Imagem', ['brightness', 'contrast', 'saturation', 'hue', 'sharpness']),
            ('Exposição', ['iris', 'gain', 'shutter_speed', 'exposure_compensation_value']),
            ('Balanço de branco', ['red_gain', 'blue_gain']),
            ('Processamento e orientação', ['noise_reduction'])]
        self._widgets = {}
        for title, fields in groups:
            group = QGroupBox(title)
            box = QVBoxLayout(group)
            if title == 'Exposição':
                self.cb_exposure_mode = QComboBox()
                self.cb_exposure_mode.addItems(['Automático', 'Manual', 'Prioridade de abertura', 'Prioridade de obturador'])
                box.addWidget(self.cb_exposure_mode)
                self._widgets['exposure_mode'] = self.cb_exposure_mode
                self.cb_exposure_mode.currentIndexChanged.connect(lambda i: self._on_setting_changed('exposure_mode', self.EXPOSURE[i]))
            if title == 'Balanço de branco':
                self.cb_wb_mode = QComboBox()
                self.cb_wb_mode.addItems(['Automático', 'Interior', 'Exterior', 'Manual', 'Uma calibração'])
                box.addWidget(self.cb_wb_mode)
                self._widgets['white_balance_mode'] = self.cb_wb_mode
                self.cb_wb_mode.currentIndexChanged.connect(lambda i: self._on_setting_changed('white_balance_mode', self.WHITE_BALANCE[i]))
            for name in fields:
                label, minimum, maximum, attr = self.ROWS[name]
                widget = _NumericSettingRow(label, minimum, maximum, int(getattr(self._current_settings, name)))
                setattr(self, attr, widget)
                self._widgets[name] = widget
                widget.value_changed.connect(lambda v, n=name: self._on_setting_changed(n, v))
                box.addWidget(widget)
            if title == 'Processamento e orientação':
                for name, label in [('blc', 'Compensar contraluz'), ('wdr', 'Ampliar alcance dinâmico'),
                    ('flip', 'Inverter verticalmente'), ('mirror', 'Espelhar horizontalmente')]:
                    widget = QCheckBox(label)
                    setattr(self, 'chk_' + name, widget)
                    self._widgets[name] = widget
                    widget.toggled.connect(lambda v, n=name: self._on_setting_changed(n, v))
                    box.addWidget(widget)
            gl.addWidget(group)
        gl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        row = QHBoxLayout()
        self.btn_undo, self.btn_redo = QPushButton('Desfazer'), QPushButton('Refazer')
        self.btn_undo.clicked.connect(self._do_undo)
        self.btn_redo.clicked.connect(self._do_redo)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)
        layout.addLayout(row)
        self._settings_history.history_changed.connect(self._on_history_changed)
        self._on_history_changed(False, False)
        self.set_supported_fields(set())

    def set_supported_fields(self, fields):
        self._support = set(fields)
        self.btn_apply.setEnabled(bool(fields))
        self.btn_read.setEnabled(bool(fields))
        self._update_visibility()
        self.status.setText('Edite os valores e clique em Aplicar ajustes. Campos indisponíveis ficam desativados.' if fields else
            'Ajustes indisponíveis. Exigem uma câmera compatível com a API HTTP Bolin/GXX-ISP.')

    def _update_visibility(self):
        for name, widget in self._widgets.items():
            enabled = name in self._support
            if name in ('iris', 'gain', 'shutter_speed'):
                mode = self._current_settings.exposure_mode
                enabled &= mode == ExposureMode.MANUAL or (name == 'iris' and mode == ExposureMode.IRIS_PRIORITY) or (name == 'shutter_speed' and mode == ExposureMode.SHUTTER_PRIORITY)
            if name in ('red_gain', 'blue_gain'):
                enabled &= self._current_settings.white_balance_mode == WhiteBalanceMode.MANUAL
            widget.setEnabled(enabled)

    def _on_setting_changed(self, name, value):
        if self._updating:
            return
        setattr(self._current_settings, name, value)
        self._settings_history.push(copy.deepcopy(self._current_settings))
        self._update_visibility()
        self.status.setText('Alterações pendentes · clique em Aplicar ajustes.')
        self.setting_changed.emit(name, value)

    def _on_apply_clicked(self):
        self.btn_apply.setEnabled(False)
        self.status.setText('Aplicando e conferindo os valores na câmera…')
        changes = {name: getattr(self._current_settings, name) for name in self._support
                   if getattr(self._current_settings, name) != getattr(self._baseline, name)}
        if not changes:
            self.btn_apply.setEnabled(bool(self._support))
            self.status.setText('Nenhuma alteração pendente.')
            return
        self.apply_all_requested.emit(changes)

    def on_applied(self, name, success):
        self.btn_apply.setEnabled(bool(self._support))
        self.status.setText('Ajustes confirmados pela câmera.' if success else
            'A câmera não confirmou os ajustes. Verifique a conexão e tente ler novamente.')

    def update_from_settings(self, settings, reset_history=True, from_camera=True):
        self._updating = True
        self._current_settings = copy.deepcopy(settings)
        if from_camera:
            self._baseline = copy.deepcopy(settings)
        for name, (_, _, _, attr) in self.ROWS.items():
            getattr(self, attr).set_value(int(getattr(settings, name)))
        self.cb_exposure_mode.setCurrentIndex(self.EXPOSURE.index(settings.exposure_mode))
        self.cb_wb_mode.setCurrentIndex(self.WHITE_BALANCE.index(settings.white_balance_mode))
        for name in ('blc', 'wdr', 'flip', 'mirror'):
            getattr(self, 'chk_' + name).setChecked(getattr(settings, name))
        self._updating = False
        self._update_visibility()
        if reset_history:
            self._settings_history.clear()
            self._settings_history.push(copy.deepcopy(settings))
        self.status.setText('Valores carregados. Edite e aplique quando estiver pronto.')

    def _on_history_changed(self, undo, redo):
        self.btn_undo.setEnabled(undo)
        self.btn_redo.setEnabled(redo)

    def _do_undo(self):
        state = self._settings_history.undo()
        if state is not None:
            self.update_from_settings(state, reset_history=False, from_camera=False)
            self.status.setText('Alterações pendentes · clique em Aplicar ajustes.')

    def _do_redo(self):
        state = self._settings_history.redo()
        if state is not None:
            self.update_from_settings(state, reset_history=False, from_camera=False)
            self.status.setText('Alterações pendentes · clique em Aplicar ajustes.')

    def get_current_settings(self):
        return copy.deepcopy(self._current_settings)
