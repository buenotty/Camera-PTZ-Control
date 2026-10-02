import ipaddress
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QPushButton, QFormLayout, QComboBox, QMessageBox)
from src.core.models import CameraConfig
from src.core.discovery import discover_cameras
from src.core.bolin_api import BolinAPIClient
from src.core.visca_client import VISCAClient


class DiscoveryThread(QThread):
    cameras_found = Signal(object)
    error = Signal(str)

    def run(self):
        try:
            self.cameras_found.emit(discover_cameras(cancelled=self.isInterruptionRequested))
        except OSError:
            self.error.emit('Não foi possível buscar nesta rede. Você pode informar o IP manualmente.')


class ConnectionTestThread(QThread):
    test_finished = Signal(bool, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        config = self.config
        http = BolinAPIClient(config.ip, config.http_port, config.username, config.password)
        visca = VISCAClient(config.ip, config.visca_port)
        try:
            http_ok = http.connect()
            visca_ok = visca.connect() and visca.get_zoom_position() is not None
            protocols = ', '.join(name for name, ok in [('HTTP', http_ok), ('VISCA', visca_ok)] if ok)
            self.test_finished.emit(bool(protocols), 'Resposta confirmada: ' + protocols if protocols else
                'Sem resposta compatível. Confira credenciais, portas e se está na mesma rede da câmera.')
        finally:
            visca.disconnect()
            http.disconnect()


class ConnectionDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle('Conectar câmera')
        self.setMinimumWidth(500)
        self.test_thread = None
        self.discovery_thread = None
        config = config or CameraConfig()
        layout = QVBoxLayout(self)
        title = QLabel('Sua câmera, no seu controle')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        help_label = QLabel('Conecte este computador à mesma rede da câmera.\nBusque câmeras ONVIF ou informe o IP manualmente.')
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        row = QHBoxLayout()
        self.camera_list = QComboBox()
        self.camera_list.setPlaceholderText('Câmeras encontradas na rede')
        self.camera_list.currentIndexChanged.connect(self._select_camera)
        self.btn_discover = QPushButton('Buscar câmeras')
        self.btn_discover.clicked.connect(self._discover)
        row.addWidget(self.camera_list, 1)
        row.addWidget(self.btn_discover)
        layout.addLayout(row)
        form = QFormLayout()
        self.le_ip = QLineEdit(config.ip)
        self.le_ip.setPlaceholderText('Ex.: 192.168.1.100')
        self.le_user = QLineEdit(config.username)
        self.le_password = QLineEdit(config.password)
        self.le_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_password.setPlaceholderText('Senha da sua câmera')
        self.le_rtsp_url = QLineEdit(config.rtsp_url)
        self.le_rtsp_url.setPlaceholderText('Opcional: URL RTSP indicada pelo fabricante')
        self.sb_http = self._port(config.http_port)
        self.sb_visca = self._port(config.visca_port)
        self.sb_rtsp = self._port(config.rtsp_port)
        for label, widget in [('IP da câmera', self.le_ip), ('Usuário', self.le_user), ('Senha', self.le_password),
            ('HTTP', self.sb_http), ('VISCA / UDP', self.sb_visca), ('RTSP', self.sb_rtsp), ('Stream personalizado', self.le_rtsp_url)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        self.lbl_status = QLabel('Credenciais usadas somente nesta sessão.')
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        buttons = QHBoxLayout()
        self.btn_test = QPushButton('Testar conexão')
        self.btn_test.clicked.connect(self._test_connection)
        self.btn_connect = QPushButton('Conectar')
        self.btn_connect.setObjectName('primaryButton')
        self.btn_connect.clicked.connect(self._accept_connection)
        cancel = QPushButton('Cancelar')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_test)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.btn_connect)
        layout.addLayout(buttons)

    @staticmethod
    def _port(value):
        widget = QSpinBox()
        widget.setRange(1, 65535)
        widget.setValue(value)
        return widget

    def _validate_ip(self):
        try:
            ipaddress.IPv4Address(self.le_ip.text().strip())
            if self.le_rtsp_url.text() and not self.le_rtsp_url.text().startswith('rtsp://'):
                raise ValueError()
            return True
        except ValueError:
            QMessageBox.warning(self, 'Verifique os dados', 'Informe um IPv4 válido e, se usar stream personalizado, uma URL rtsp://.')
            return False

    def _discover(self):
        self.btn_discover.setEnabled(False)
        self.lbl_status.setText('Buscando câmeras ONVIF na rede local…')
        self.discovery_thread = DiscoveryThread(self)
        self.discovery_thread.cameras_found.connect(self._found)
        self.discovery_thread.error.connect(self.lbl_status.setText)
        self.discovery_thread.finished.connect(lambda: self.btn_discover.setEnabled(True))
        self.discovery_thread.start()

    def _found(self, cameras):
        self.camera_list.clear()
        for camera in cameras:
            self.camera_list.addItem(f'{camera.name} · {camera.ip}', camera)
        self.lbl_status.setText(f'{len(cameras)} câmera(s) encontrada(s).' if cameras else
            'Nenhuma câmera ONVIF encontrada. Câmeras antigas podem exigir o IP manual.')

    def _select_camera(self, index):
        camera = self.camera_list.itemData(index)
        if camera:
            self.le_ip.setText(camera.ip)
            self.sb_http.setValue(camera.http_port)

    def _test_connection(self):
        if not self._validate_ip():
            return
        self.btn_test.setEnabled(False)
        self.lbl_status.setText('Verificando resposta e autenticação…')
        self.test_thread = ConnectionTestThread(self.get_config(), self)
        self.test_thread.test_finished.connect(self._on_test_finished)
        self.test_thread.finished.connect(lambda: self.btn_test.setEnabled(True))
        self.test_thread.start()

    def _on_test_finished(self, success, message):
        self.lbl_status.setText(message)

    def _accept_connection(self):
        if self._validate_ip():
            self.accept()

    def done(self, result):
        for thread in (self.test_thread, self.discovery_thread):
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.wait()
        super().done(result)

    def get_config(self):
        return CameraConfig(ip=self.le_ip.text().strip(), http_port=self.sb_http.value(),
            visca_port=self.sb_visca.value(), rtsp_port=self.sb_rtsp.value(),
            username=self.le_user.text().strip(), password=self.le_password.text(), rtsp_url=self.le_rtsp_url.text().strip())
