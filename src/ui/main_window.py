import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QScrollArea, QToolBar, QStatusBar, QLabel, QMenuBar, QMenu,
    QApplication, QSizePolicy, QSpacerItem, QMessageBox, QTabWidget, QPushButton, QFrame, QComboBox
)
from PySide6.QtCore import Qt, QSettings, Slot, Signal, QEvent
from PySide6.QtGui import QAction, QKeySequence, QIcon, QKeyEvent

from src.ui.video_panel import VideoPanel
from src.ui.ptz_controls import PTZControlPanel
from src.ui.focus_controls import FocusControlPanel
from src.ui.image_settings import ImageSettingsPanel
from src.ui.preset_manager import PresetManagerPanel
from src.ui.profile_manager import ProfileManagerWidget
from src.ui.recording_controls import RecordingControls
from src.ui.keyboard_overlay import KeyboardOverlayDialog
from src.ui.styles.theme import ThemeManager
from src.ui.connection_dialog import ConnectionDialog

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    Janela principal da aplicação PTZ Control.
    Integra todos os painéis e gerencia o layout da interface.
    """

    # Emitido quando o usuário confirma uma nova configuração de conexão
    diagnostic_requested = Signal()
    emergency_requested = Signal()
    disconnect_requested = Signal()
    connection_requested = Signal(object)  # CameraConfig

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PTZ Control")
        self.setMinimumSize(1000, 680)
        self.resize(1440, 900)
        self._camera_config = None

        self._keyboard_handler = None
        self._theme_manager = ThemeManager()

        # Instanciar os componentes principais
        self._video_panel = VideoPanel()
        self._ptz_controls = PTZControlPanel()
        self._focus_controls = FocusControlPanel()
        self._image_settings = ImageSettingsPanel()
        self._preset_manager = PresetManagerPanel()
        self._recording_controls = RecordingControls()
        self._profile_manager = ProfileManagerWidget()

        # Configurar interface
        self._setup_ui()
        self._setup_menus()
        self._setup_status_bar()


        # Aplicar tema padrão
        self._theme_manager.apply(QApplication.instance())
        self._theme_manager.theme_changed.connect(lambda _: self._theme_manager.apply(QApplication.instance()))

        # Restaurar configurações de janela
        self._load_geometry()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(16)
        header = QFrame()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(18, 14, 18, 14)
        title = QVBoxLayout()
        brand = QLabel("PTZ Control")
        brand.setObjectName("brand")
        subtitle = QLabel("Um novo jeito de enquadrar sua transmissão")
        subtitle.setObjectName("muted")
        title.addWidget(brand)
        title.addWidget(subtitle)
        row.addLayout(title)
        row.addStretch()
        self.camera_badge = QLabel("●  Nenhuma câmera conectada")
        self.camera_badge.setObjectName("muted")
        row.addWidget(self.camera_badge)
        self.connect_button = QPushButton("Conectar câmera")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self._open_connection_dialog)
        row.addWidget(self.connect_button)
        self.emergency_button = QPushButton("■  Parar · Espaço")
        self.emergency_button.setObjectName("emergencyButton")
        self.emergency_button.clicked.connect(self.emergency_requested)
        row.addWidget(self.emergency_button)
        layout.addWidget(header)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        video_header = QHBoxLayout()
        label = QLabel("MONITOR")
        label.setObjectName("muted")
        video_header.addWidget(label)
        video_header.addStretch()
        help_label = QLabel("Arraste para mover · role para zoom")
        help_label.setObjectName("muted")
        video_header.addWidget(help_label)
        ll.addLayout(video_header)
        self._video_panel.setMinimumSize(420, 280)
        ll.addWidget(self._video_panel, 1)
        ll.addWidget(self._recording_controls)
        self._preset_manager.setMinimumHeight(160)
        self._preset_manager.setMaximumHeight(210)
        ll.addWidget(self._preset_manager)
        self._splitter.addWidget(left)
        self._right_tabs = QTabWidget()
        self._right_tabs.setMinimumWidth(360)
        self._right_tabs.setMaximumWidth(550)
        self._right_tabs.setDocumentMode(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls = QWidget()
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(4, 12, 4, 4)
        cl.addWidget(self._ptz_controls)
        cl.addWidget(self._focus_controls)
        cl.addStretch()
        scroll.setWidget(controls)
        self._right_tabs.addTab(scroll, "Movimento")
        self._right_tabs.addTab(self._image_settings, "Imagem")
        profiles = QWidget()
        pl = QVBoxLayout(profiles)
        title = QLabel("Seus perfis de imagem")
        title.setObjectName("sectionTitle")
        pl.addWidget(title)
        hint = QLabel("Salve ajustes para diferentes ambientes. Carregar um perfil prepara os valores; clique em Aplicar ajustes na aba Imagem para enviá-los à câmera.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        pl.addWidget(hint)
        pl.addWidget(self._profile_manager)
        pl.addStretch()
        self._right_tabs.addTab(profiles, "Perfis")
        self._splitter.addWidget(self._right_tabs)
        self._splitter.setSizes([1000, 380])
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        layout.addWidget(self._splitter, 1)

    def _setup_menus(self):
        camera = self.menuBar().addMenu("Câmera")
        self.action_connect = camera.addAction("Conectar / configurar", self._open_connection_dialog)
        self.action_connect.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.action_disconnect = camera.addAction("Desconectar", self.disconnect_requested.emit)
        camera.addAction("Exportar diagnóstico", self.diagnostic_requested.emit)
        camera.addSeparator()
        camera.addAction("Sair", self.close)
        view = self.menuBar().addMenu("Visualizar")
        view.addAction("Tema claro / escuro", self._toggle_theme)
        self.action_toggle_grid = view.addAction("Grade de enquadramento")
        self.action_toggle_grid.setCheckable(True)
        self.action_toggle_grid.toggled.connect(self._video_panel.set_grid_visible)
        fullscreen = view.addAction("Tela cheia", self._toggle_fullscreen)
        fullscreen.setShortcut(QKeySequence("F11"))
        help_menu = self.menuBar().addMenu("Ajuda")
        shortcuts = help_menu.addAction("Atalhos", self._show_keyboard_shortcuts)
        shortcuts.setShortcut(QKeySequence("F1"))
        help_menu.addAction("Sobre", self._show_about)

    def _setup_status_bar(self):
        """Configura a barra de status."""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)

        # Componentes do Status
        self.lbl_connection_dot = QLabel("●")
        self.lbl_connection_dot.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_connection_text = QLabel("Desconectado")
        self.lbl_ip = QLabel("-")
        self.lbl_protocol = QLabel("-")
        self.lbl_input_mode = QLabel("Híbrido")
        self.lbl_velocity = QLabel("Vel: 0%")

        statusbar.addPermanentWidget(self.lbl_connection_dot)
        statusbar.addPermanentWidget(self.lbl_connection_text)
        statusbar.addPermanentWidget(QLabel("│"))
        statusbar.addPermanentWidget(self.lbl_ip)
        statusbar.addPermanentWidget(QLabel("│"))
        statusbar.addPermanentWidget(self.lbl_protocol)
        statusbar.addPermanentWidget(QLabel("│"))
        statusbar.addPermanentWidget(self.lbl_input_mode)
        statusbar.addPermanentWidget(QLabel("│"))
        statusbar.addPermanentWidget(self.lbl_velocity)

    def _load_geometry(self):
        """Carrega a geometria e estado da janela das configurações."""
        settings = QSettings("PTZ Control", "PTZControl")
        geometry = settings.value("mainwindow/geometry")
        state = settings.value("mainwindow/state")
        splitter_state = settings.value("mainwindow/splitter")

        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        if splitter_state:
            self._splitter.restoreState(splitter_state)

    def _save_geometry(self):
        """Salva a geometria e estado da janela nas configurações."""
        settings = QSettings("PTZ Control", "PTZControl")
        settings.setValue("mainwindow/geometry", self.saveGeometry())
        settings.setValue("mainwindow/state", self.saveState())
        settings.setValue("mainwindow/splitter", self._splitter.saveState())

    def closeEvent(self, event):
        """Captura o evento de fechamento para salvar o estado da janela."""
        self.emergency_requested.emit()
        self._save_geometry()
        super().closeEvent(event)

    # --- Ações dos Menus ---

    @Slot()
    def _open_connection_dialog(self):
        """Abre o diálogo de configuração de conexão com a câmera."""
        dialog = ConnectionDialog(self, config=self._camera_config)
        if dialog.exec():
            config = dialog.get_config()
            self.connection_requested.emit(config)

    @Slot()
    def _toggle_theme(self):
        """Alterna entre os temas claro e escuro."""
        self._theme_manager.toggle()


    @Slot()
    def _toggle_fullscreen(self):
        """Alterna o modo de tela cheia."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    @Slot()
    def _show_keyboard_shortcuts(self):
        """Exibe o diálogo de atalhos de teclado."""
        dialog = KeyboardOverlayDialog(self)
        dialog.exec()

    @Slot()
    def _show_about(self):
        """Exibe informações sobre o aplicativo."""
        QMessageBox.about(self, "Sobre o PTZ Control", "PTZ Control\nDesenvolvido em Python/PySide6\nPara câmeras PTZ Bolin (VISCA).")

    # --- Métodos Públicos para Acesso aos Componentes ---

    def get_video_panel(self) -> VideoPanel:
        return self._video_panel

    def get_ptz_controls(self) -> PTZControlPanel:
        return self._ptz_controls

    def get_focus_controls(self) -> FocusControlPanel:
        return self._focus_controls

    def get_image_settings(self) -> ImageSettingsPanel:
        return self._image_settings

    def get_preset_manager(self) -> PresetManagerPanel:
        return self._preset_manager

    def get_recording_controls(self) -> RecordingControls:
        return self._recording_controls

    def get_profile_manager(self) -> ProfileManagerWidget:
        return self._profile_manager

    # --- Métodos de Atualização de UI ---

    def update_connection_status(self, connected: bool, ip: str = "", protocol: str = ""):
        """Atualiza os indicadores de conexão na barra de status."""
        self.camera_badge.setText(f"●  {ip}" if connected else "●  Nenhuma câmera conectada")
        self.connect_button.setText("Configurar câmera" if connected else "Conectar câmera")
        self.action_disconnect.setEnabled(connected)
        self._ptz_controls.setEnabled(connected)
        self._preset_manager.setEnabled(connected)
        self._recording_controls.setEnabled(connected)
        if connected:
            self.lbl_connection_dot.setStyleSheet("color: green; font-weight: bold;")
            self.lbl_connection_text.setText("Conectado")
            self.lbl_ip.setText(ip)
            self.lbl_protocol.setText(protocol)
        else:
            self.lbl_connection_dot.setStyleSheet("color: red; font-weight: bold;")
            self.lbl_connection_text.setText("Desconectado")
            self.lbl_ip.setText("-")
            self.lbl_protocol.setText("-")

    def update_input_mode(self, mode_str: str):
        """Atualiza o modo de entrada exibido na barra de status."""
        self.lbl_input_mode.setText(mode_str)

    def update_velocity_info(self, pan_pct: int, tilt_pct: int, zoom_pct: int):
        """Atualiza a informação de velocidade na barra de status."""
        # Calculando uma média ou mostrando o maior valor
        max_vel = max(pan_pct, tilt_pct)
        self.lbl_velocity.setText(f"Vel: {max_vel:.0f}%")

    # --- Gerenciamento de Teclado ---

    def set_keyboard_handler(self, handler):
        """Define o tratador de eventos de teclado e instala o filtro global."""
        self._keyboard_handler = handler
        # Instalar filtro de eventos na aplicação para interceptar teclas PTZ
        # antes que qualquer widget filho (sliders, joystick, etc.) as consuma
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def eventFilter(self, obj, event):
        """
        Filtro global de eventos que intercepta teclas PTZ com segurança.
        Libera o teclado quando o foco está em caixas de entrada de texto/números
        e interrompe movimentos quando a janela perde o foco.
        """
        if not self._keyboard_handler:
            return super().eventFilter(obj, event)

        evt_type = event.type()

        # Se a janela for desativada ou perder o foco do sistema, limpar todas as teclas
        if evt_type in (QEvent.Type.WindowDeactivate, QEvent.Type.ApplicationDeactivate):
            self._keyboard_handler.clear_all_keys()
            self.emergency_requested.emit()
            return super().eventFilter(obj, event)

        if evt_type == QEvent.Type.KeyRelease and event.key() in self._keyboard_handler._pressed_keys:
            return self._keyboard_handler.handle_key_release(event)
        if QApplication.activeModalWidget() is not None:
            return super().eventFilter(obj, event)
        if not self._ptz_controls.isEnabled():
            return super().eventFilter(obj, event)
        # Se o widget focado for um campo de digitação (SpinBox, LineEdit, TextEdit),
        # permitir que o usuário digite livremente sem disparar movimentos PTZ
        from PySide6.QtWidgets import QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit
        if evt_type == QEvent.Type.FocusIn and isinstance(obj, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)):
            self.emergency_requested.emit()
        if isinstance(obj, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit, QComboBox)):
            # Se pressionar Escape dentro de um campo, tira o foco
            if evt_type == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                obj.clearFocus()
                return True
            return super().eventFilter(obj, event)

        if evt_type == QEvent.Type.KeyPress:
            if self._keyboard_handler.handle_key_press(event):
                return True
        elif evt_type == QEvent.Type.KeyRelease:
            if self._keyboard_handler.handle_key_release(event):
                return True

        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        """Limpa teclas quando o status de ativação da janela mudar."""
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if self._keyboard_handler:
                self._keyboard_handler.clear_all_keys()
        super().changeEvent(event)

    def keyPressEvent(self, event):
        """Repassa ao handler se não consumido pelo eventFilter."""
        if self._keyboard_handler and self._keyboard_handler.handle_key_press(event):
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Repassa ao handler se não consumido pelo eventFilter."""
        if self._keyboard_handler and self._keyboard_handler.handle_key_release(event):
            event.accept()
        else:
            super().keyReleaseEvent(event)
