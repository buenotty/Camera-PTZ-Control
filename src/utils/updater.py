import json
import os
import sys
import subprocess
import tempfile
import zipfile
import requests
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread
import typing

# Fallback logger se não existir
import logging
logger = logging.getLogger(__name__)

class UpdateInfo:
    """Informações sobre uma atualização disponível."""
    def __init__(self, version: str, download_url: str, release_notes: str, file_size: int):
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.file_size = file_size

class UpdateCheckThread(QThread):
    """Thread para buscar atualização sem travar a interface."""
    update_found = Signal(object) # UpdateInfo
    no_update = Signal()
    error = Signal(str)

    def __init__(self, current_version: str, update_url: str):
        super().__init__()
        self.current_version = current_version
        self.update_url = update_url

    def run(self):
        try:
            if not self.update_url or "OWNER" in self.update_url:
                self.no_update.emit()
                return

            headers = {"Accept": "application/vnd.github.v3+json"}
            response = requests.get(self.update_url, headers=headers, timeout=10)
            if response.status_code == 404:
                self.no_update.emit()
                return
            response.raise_for_status()
            data = response.json()

            # Assumindo formato do Github Releases ou endpoint customizado
            latest_version = data.get("tag_name", "").lstrip("v")
            if not latest_version:
                latest_version = data.get("version", "")

            if not latest_version:
                self.error.emit("Formato de resposta inválido.")
                return

            if self._compare_versions(self.current_version, latest_version):
                assets = data.get("assets", [])
                download_url = ""
                file_size = 0
                if assets:
                    download_url = assets[0].get("browser_download_url", "")
                    file_size = assets[0].get("size", 0)
                else:
                    # Endpoint customizado fallback
                    download_url = data.get("download_url", "")
                    file_size = data.get("file_size", 0)

                release_notes = data.get("body", "Sem notas de versão.")
                info = UpdateInfo(latest_version, download_url, release_notes, file_size)
                self.update_found.emit(info)
            else:
                self.no_update.emit()
        except Exception as e:
            logger.error(f"Erro ao buscar atualizações: {e}")
            self.error.emit(str(e))

    def _compare_versions(self, current: str, remote: str) -> bool:
        """
        Retorna True se remote for maior que current.
        """
        try:
            curr_parts = tuple(map(int, current.split(".")))
            rem_parts = tuple(map(int, remote.split(".")))
            return rem_parts > curr_parts
        except ValueError:
            return False

class DownloadUpdateThread(QThread):
    """Thread para realizar o download do arquivo de atualização."""
    progress = Signal(int, int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.dest_path = ""

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            temp_dir = tempfile.gettempdir()
            filename = self.url.split("/")[-1]
            if not filename:
                filename = "update.zip"

            self.dest_path = os.path.join(temp_dir, filename)

            downloaded = 0
            with open(self.dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)

            self.finished.emit(self.dest_path)
        except Exception as e:
            logger.error(f"Erro no download da atualização: {e}")
            self.error.emit(str(e))

class UpdateChecker(QObject):
    """Sistema de verificação e instalação de atualizações OTA."""
    update_available = Signal(object)       # UpdateInfo
    no_update = Signal()
    check_failed = Signal(str)              # error message
    download_progress = Signal(int, int)    # bytes_downloaded, total_bytes
    download_complete = Signal(str)         # path to downloaded file
    download_failed = Signal(str)           # error message

    def __init__(self, current_version: str = "", update_url: str = ""):
        super().__init__()
        if not current_version or not update_url:
            current_version, update_url = self.get_current_version_info()

        self.current_version = current_version
        self.update_url = update_url
        self._check_thread = None
        self._download_thread = None

    def get_current_version_info(self) -> typing.Tuple[str, str]:
        """Lê informações de versão do arquivo version.json na raiz."""
        try:
            base_dir = Path(__file__).parent.parent.parent
            version_file = base_dir / "version.json"
            if version_file.exists():
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0"), data.get("update_url", "")
        except Exception as e:
            logger.error(f"Erro ao ler version.json: {e}")
        return "1.0.0", ""

    def check_for_updates(self) -> None:
        """Inicia a verificação de atualizações em background."""
        if not self.update_url:
            self.check_failed.emit("URL de atualização não configurada.")
            return

        self._check_thread = UpdateCheckThread(self.current_version, self.update_url)
        self._check_thread.update_found.connect(self.update_available.emit)
        self._check_thread.no_update.connect(self.no_update.emit)
        self._check_thread.error.connect(self.check_failed.emit)
        self._check_thread.start()

    def download_update(self, info: UpdateInfo) -> None:
        """Inicia o download do arquivo de atualização."""
        if not info.download_url:
            self.download_failed.emit("URL de download inválida.")
            return

        self._download_thread = DownloadUpdateThread(info.download_url)
        self._download_thread.progress.connect(self.download_progress.emit)
        self._download_thread.finished.connect(self.download_complete.emit)
        self._download_thread.error.connect(self.download_failed.emit)
        self._download_thread.start()

    def install_update(self, filepath: str) -> None:
        """
        Inicia a instalação da atualização baixada.
        Se for exe, executa. Se for zip, pode necessitar script de extração.
        """
        try:
            if filepath.endswith('.exe'):
                subprocess.Popen([filepath])
                sys.exit(0)
            elif filepath.endswith('.zip'):
                # Em um app real, precisaríamos de um launcher externo para substituir os arquivos
                # já que não podemos substituir arquivos em uso (arquivos do app rodando).
                # Como implementação base:
                logger.info(f"Arquivo zip baixado em {filepath}. Requer script de extração.")
                sys.exit(0)
            else:
                logger.error("Formato de arquivo não suportado.")
        except Exception as e:
            logger.error(f"Erro ao instalar atualização: {e}")
