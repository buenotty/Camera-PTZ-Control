from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QProgressBar, QWidget
)
from PySide6.QtCore import Qt, QSettings
import typing
from src.utils.updater import UpdateChecker, UpdateInfo

class UpdateDialog(QDialog):
    """
    Diálogo de notificação de nova versão, mostrando notas de lançamento e
    progresso de download.
    """
    def __init__(self, current_version: str, update_info: UpdateInfo, checker: UpdateChecker, parent: typing.Optional[QWidget] = None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_info = update_info
        self.checker = checker
        self.downloaded_file = ""

        self.setWindowTitle("Atualização Disponível")
        self.setFixedSize(500, 400)
        self.setModal(True)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Configura a interface visual do diálogo."""
        layout = QVBoxLayout(self)

        # Título
        title = QLabel(f"Nova versão {self.update_info.version} disponível!")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: palette(highlight);")
        layout.addWidget(title)

        # Versões
        ver_layout = QHBoxLayout()
        ver_layout.addWidget(QLabel(f"Versão atual: {self.current_version}"))
        ver_layout.addStretch()
        ver_layout.addWidget(QLabel(f"Nova versão: {self.update_info.version}"))
        layout.addLayout(ver_layout)

        # Notas de lançamento
        layout.addWidget(QLabel("Notas de Lançamento:"))
        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setMarkdown(self.update_info.release_notes)
        layout.addWidget(self.notes_browser)

        # Barra de progresso (oculta inicialmente)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Botões
        self.btn_layout = QHBoxLayout()

        self.btn_ignore = QPushButton("Ignorar Esta Versão")
        self.btn_ignore.clicked.connect(self._ignore_version)

        self.btn_later = QPushButton("Depois")
        self.btn_later.clicked.connect(self.reject)

        self.btn_update = QPushButton("Atualizar Agora")
        self.btn_update.setStyleSheet("background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold;")
        self.btn_update.clicked.connect(self._start_download)

        self.btn_install = QPushButton("Instalar e Reiniciar")
        self.btn_install.setStyleSheet("background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold;")
        self.btn_install.setVisible(False)
        self.btn_install.clicked.connect(self._install_update)

        self.btn_layout.addWidget(self.btn_ignore)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.btn_later)
        self.btn_layout.addWidget(self.btn_update)
        self.btn_layout.addWidget(self.btn_install)

        layout.addLayout(self.btn_layout)

    def _connect_signals(self) -> None:
        """Conecta os sinais do UpdateChecker."""
        self.checker.download_progress.connect(self._update_progress)
        self.checker.download_complete.connect(self._download_finished)
        self.checker.download_failed.connect(self._download_error)

    def _start_download(self) -> None:
        """Inicia o download da atualização."""
        self.btn_update.setEnabled(False)
        self.btn_ignore.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Baixando atualização...")
        self.checker.download_update(self.update_info)

    def _update_progress(self, downloaded: int, total: int) -> None:
        """Atualiza a barra de progresso."""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_label.setText(f"Baixado: {mb_down:.2f} MB / {mb_total:.2f} MB")

    def _download_finished(self, filepath: str) -> None:
        """Callback acionado quando o download termina com sucesso."""
        self.downloaded_file = filepath
        self.progress_bar.setValue(100)
        self.status_label.setText("Download concluído! Pronto para instalar.")
        self.btn_update.setVisible(False)
        self.btn_install.setVisible(True)
        self.btn_later.setText("Cancelar")

    def _download_error(self, error: str) -> None:
        """Callback acionado em caso de erro no download."""
        self.status_label.setText(f"Erro no download: {error}")
        self.btn_update.setEnabled(True)
        self.btn_ignore.setEnabled(True)

    def _install_update(self) -> None:
        """Inicia o processo de instalação."""
        if self.downloaded_file:
            self.checker.install_update(self.downloaded_file)

    def _ignore_version(self) -> None:
        """Salva a versão ignorada nas configurações e fecha."""
        settings = QSettings("SuaEmpresa", "PTZControl")
        settings.setValue("ignored_version", self.update_info.version)
        self.accept()
