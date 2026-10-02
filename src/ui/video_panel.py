import sys
try:
    import vlc
except (ImportError, OSError):
    vlc = None
import time
import math
import shutil
import ctypes
import threading
import time
from pathlib import Path
from typing import Optional
from src.core.video_decoder import FFmpegPreview

from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QRect, QProcess
from PySide6.QtGui import QMouseEvent, QWheelEvent, QCursor, QColor, QPalette, QPainter, QPen, QImage
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout


class VideoOverlay(QWidget):
    """
    Overlay transparente para capturar eventos de mouse em cima do vídeo.
    """
    mouse_drag_started = Signal(int, int)
    mouse_drag_moved = Signal(float, float)
    mouse_drag_ended = Signal()
    mouse_scroll = Signal(int)
    mouse_double_clicked = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self._dragging = False
        self._origin = QPoint()
        self._deadzone = 15
        self.grid_visible = False

    def paintEvent(self, event) -> None:
        if self.grid_visible:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
            for fraction in (1 / 3, 2 / 3):
                x, y = int(self.width() * fraction), int(self.height() * fraction)
                painter.drawLine(x, 0, x, self.height())
                painter.drawLine(0, y, self.width(), y)


    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._origin = event.pos()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.mouse_drag_started.emit(self._origin.x(), self._origin.y())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            current_pos = event.pos()
            dx = current_pos.x() - self._origin.x()
            dy = current_pos.y() - self._origin.y()

            # Aplicar deadzone
            dist = math.hypot(dx, dy)
            if dist > self._deadzone:
                # Normalizar para [-1.0, 1.0] (baseado em um deslocamento máximo de ~200 pixels)
                max_dist = 200.0
                norm_x = max(-1.0, min(1.0, dx / max_dist))
                # Inverter Y para que mover o mouse para cima seja positivo
                norm_y = max(-1.0, min(1.0, -dy / max_dist))
                self.mouse_drag_moved.emit(norm_x, norm_y)
            else:
                self.mouse_drag_moved.emit(0.0, 0.0)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.mouse_drag_ended.emit()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta != 0:
            self.mouse_scroll.emit(delta)
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_double_clicked.emit(event.pos().x(), event.pos().y())
        super().mouseDoubleClickEvent(event)


class VideoCanvas(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = QImage()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#070b12'))
        if not self.frame.isNull():
            size = self.frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect((self.width() - size.width()) // 2, (self.height() - size.height()) // 2,
                           size.width(), size.height())
            painter.drawImage(target, self.frame)


class VideoPanel(QWidget):
    """
    Painel de vídeo que renderiza stream RTSP usando LibVLC e gerencia interação.
    """
    # Re-emit overlay signals
    mouse_drag_started = Signal(int, int)
    mouse_drag_moved = Signal(float, float)
    mouse_drag_ended = Signal()
    mouse_scroll = Signal(int)
    mouse_double_clicked = Signal(int, int)
    resized = Signal(int, int)

    # Error signal
    playback_error = Signal(str)
    recording_changed = Signal(bool)
    _frame_ready = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._url: str = ""
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._player: Optional[vlc.MediaPlayer] = None
        self._instance: Optional[vlc.Instance] = None

        self._ffmpeg_preview = None
        self._preview_generation = 0
        self._recorder = None
        self._recording = False
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._frame_pending = False
        self._frame_ready.connect(self._present_frame)
        self._setup_ui()
        try:
            self._setup_vlc()
        except (OSError, NameError, AttributeError):
            self._status_label.setText("VLC não encontrado · instale o VLC para reproduzir vídeo")
        self._setup_reconnect_timer()

    def _setup_ui(self) -> None:
        self.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container do vídeo — WA_NativeWindow dá ao VLC um HWND nativo.
        self._video_frame = VideoCanvas(self)
        layout.addWidget(self._video_frame)

        # Overlay para captura de mouse
        self._overlay = VideoOverlay(self)
        self._overlay.mouse_drag_started.connect(self.mouse_drag_started)
        self._overlay.mouse_drag_moved.connect(self.mouse_drag_moved)
        self._overlay.mouse_drag_ended.connect(self.mouse_drag_ended)
        self._overlay.mouse_scroll.connect(self.mouse_scroll)
        self._overlay.mouse_double_clicked.connect(self.mouse_double_clicked)

        # Status HUD posicionado sobre o overlay
        self._status_label = QLabel("Aguardando conexão...", self._overlay)
        self._status_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 150); padding: 5px; border-radius: 3px;"
        )
        self._status_label.move(16, 16)
        self._status_label.adjustSize()
        self._empty_label = QLabel("MONITOR DA CÂMERA\n\nConecte sua câmera para acompanhar a transmissão", self._overlay)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #92a1b8; background: transparent; font-size: 16px;")

    def _setup_vlc(self) -> None:
        vlc_args = ["--no-audio", "--network-caching=250",
                    "--no-video-title-show", "--no-osd", "--quiet"]
        self._instance = vlc.Instance(*vlc_args)
        if not self._instance:
            self._instance = vlc.Instance()
        self._player = self._instance.media_player_new() if self._instance else None
        if self._player:
            self._setup_frame_callbacks()

    def _setup_frame_callbacks(self):
        # Qt paints the decoded preview on every platform. Avoid native VLC
        # child windows, which can obscure overlays or render a black panel.
        self._preview_width, self._preview_height = 1280, 720
        self._video_buffer = ctypes.create_string_buffer(self._preview_width * self._preview_height * 4)
        self._buffer_lock = threading.Lock()

        @vlc.CallbackDecorators.VideoLockCb
        def lock(opaque, planes):
            self._buffer_lock.acquire()
            planes[0] = ctypes.addressof(self._video_buffer)
            return None

        @vlc.CallbackDecorators.VideoUnlockCb
        def unlock(opaque, picture, planes):
            self._buffer_lock.release()

        @vlc.CallbackDecorators.VideoDisplayCb
        def display(opaque, picture):
            with self._buffer_lock:
                frame = QImage(self._video_buffer, self._preview_width, self._preview_height,
                    self._preview_width * 4, QImage.Format.Format_RGB32).copy()
            self._queue_frame(frame)

        # Retain callbacks and the buffer until playback is stopped/released.
        self._video_callbacks = (lock, unlock, display)
        self._player.video_set_callbacks(lock, unlock, display, None)
        self._player.video_set_format('RV32', self._preview_width, self._preview_height, self._preview_width * 4)

    def _queue_frame(self, frame, generation=None):
        with self._frame_lock:
            if generation is not None and generation != self._preview_generation:
                return
            self._latest_frame = frame
            notify = not self._frame_pending
            self._frame_pending = True
        if notify:
            self._frame_ready.emit()

    def _present_frame(self):
        with self._frame_lock:
            frame = self._latest_frame
            self._frame_pending = False
        if frame is not None:
            self._video_frame.frame = frame
            self._video_frame.update()
            self._empty_label.hide()
            self._status_label.setText('● Vídeo conectado')
            self._status_label.adjustSize()

    def _setup_reconnect_timer(self) -> None:
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(3000)
        self._reconnect_timer.timeout.connect(self._check_connection)

        self._reconnect_delay = QTimer(self)
        self._reconnect_delay.setInterval(1000)
        self._reconnect_delay.setSingleShot(True)
        self._reconnect_delay.timeout.connect(self._do_reconnect)

    def play(self, rtsp_url: str) -> None:
        """Inicia a reprodução do stream."""
        self._url = rtsp_url
        self._reconnect_attempts = 0
        self._preview_generation += 1
        generation = self._preview_generation
        if self._ffmpeg_preview:
            self._ffmpeg_preview.stop()
            self._ffmpeg_preview = None
        if rtsp_url.startswith('rtsp://') and shutil.which('ffmpeg'):
            if self._player:
                self._player.stop()
            self._ffmpeg_preview = FFmpegPreview(rtsp_url,
                lambda frame: self._queue_frame(frame, generation), self.playback_error.emit)
            self._ffmpeg_preview.start()
            self._status_label.setText('Conectando…')
            self._status_label.adjustSize()
            self._reconnect_timer.start()
            return
        if not self._player:
            self.playback_error.emit("Instale o VLC da mesma arquitetura do Python para reproduzir vídeo.")
            return

        media = self._instance.media_new(self._url)
        media.add_option(":no-audio")
        media.add_option(":rtsp-tcp")
        media.add_option(":avcodec-hw=none")
        media.add_option(":avcodec-threads=1")
        media.add_option(":network-caching=250")
        self._player.set_media(media)
        self._player.play()
        self._status_label.setText("Conectando...")
        self._status_label.adjustSize()
        self._reconnect_timer.start()

    def stop(self) -> None:
        """Para a reprodução."""
        self.stop_recording()
        self._preview_generation += 1
        if self._ffmpeg_preview:
            self._ffmpeg_preview.stop()
            self._ffmpeg_preview = None
        self._overlay._dragging = False
        self._reconnect_timer.stop()
        self._reconnect_delay.stop()
        if self._player:
            self._player.stop()
        with self._frame_lock:
            self._latest_frame = None
        self._video_frame.frame = QImage()
        self._video_frame.update()
        self._status_label.setText("Desconectado")
        self._status_label.adjustSize()
        self._empty_label.show()

    def is_playing(self) -> bool:
        """Retorna True se o vídeo estiver sendo reproduzido."""
        if self._ffmpeg_preview:
            return self._ffmpeg_preview.is_playing()
        if self._player:
            return self._player.is_playing() == 1 and not self._video_frame.frame.isNull()
        return False

    def reconnect(self) -> None:
        """Força a reconexão imediata do stream."""
        if self._url:
            self.stop()
            self._reconnect_attempts = 0
            self._do_reconnect()

    def _check_connection(self):
        if self._ffmpeg_preview:
            if self._ffmpeg_preview.is_playing():
                self._reconnect_attempts = 0
                return
            if self._ffmpeg_preview._thread.is_alive():
                return
            failed = True
        elif self._player:
            state = self._player.get_state()
            failed = state in (vlc.State.Error, vlc.State.Ended, vlc.State.Stopped)
            if state == vlc.State.Playing and not self._video_frame.frame.isNull():
                self._reconnect_attempts = 0
        else:
            return
        if failed:
            if self._reconnect_attempts < self._max_reconnect_attempts:
                self._status_label.setText(f"Reconectando… ({self._reconnect_attempts + 1}/{self._max_reconnect_attempts})")
                self._status_label.adjustSize()
                if not self._reconnect_delay.isActive():
                    self._reconnect_delay.start()
            else:
                self._status_label.setText('Vídeo indisponível')
                self._status_label.adjustSize()
                self.playback_error.emit('Falha ao reconectar o vídeo. Verifique URL, credenciais e rede.')
                self._reconnect_timer.stop()

    def _do_reconnect(self) -> None:
        self._reconnect_attempts += 1
        if self._url:
            if self._player:
                self._player.stop()
            attempts = self._reconnect_attempts
            self.play(self._url)
            self._reconnect_attempts = attempts

    def set_grid_visible(self, visible):
        self._overlay.grid_visible = visible
        self._overlay.update()

    def is_recording(self):
        return self._recording

    def start_recording(self, path):
        if self._recorder is not None:
            return
        if not self.is_playing() or not shutil.which('ffmpeg'):
            self.playback_error.emit('Gravação exige vídeo conectado e FFmpeg instalado.')
            self.recording_changed.emit(False)
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._recorder = QProcess(self)
        self._recorder.setProgram(shutil.which('ffmpeg'))
        self._recorder.setArguments(['-hide_banner', '-loglevel', 'error'] + (['-rtsp_transport', 'tcp'] if self._url.startswith('rtsp://') else []) + [
            '-i', self._url, '-map', '0:v:0', '-an', '-c:v', 'copy', '-progress', 'pipe:1',
            '-n', path])
        self._recorder.readyReadStandardOutput.connect(self._record_progress)
        self._recorder.errorOccurred.connect(self._record_error)
        self._recorder.finished.connect(self._record_finished)
        self._recorder.start()

    def _record_progress(self):
        if self._recorder is None:
            return
        text = bytes(self._recorder.readAllStandardOutput()).decode(errors='replace')
        for line in text.splitlines():
            if line.startswith('frame=') and int(line.split('=', 1)[1]) > 0 and not self._recording:
                self._recording = True
                self.recording_changed.emit(True)

    def _record_error(self, error):
        self.playback_error.emit('Não foi possível iniciar a gravação. Confira a instalação do FFmpeg.')
        self._record_finished(-1, None)

    def _record_finished(self, code, status):
        process, self._recorder = self._recorder, None
        self._recording = False
        self.recording_changed.emit(False)
        if process:
            process.deleteLater()
        if code not in (0, 255):
            self.playback_error.emit('A gravação falhou. Confira o stream e a pasta de destino.')

    def stop_recording(self):
        process = self._recorder
        if process:
            process.write(b'q\n')
            if not process.waitForFinished(2000):
                process.terminate()
                if not process.waitForFinished(1000):
                    process.kill()
                    process.waitForFinished(1000)

    def shutdown(self):
        self.stop()
        if self._player:
            self._player.release()
            self._player = None
        if self._instance:
            self._instance.release()
            self._instance = None

    def resizeEvent(self, event) -> None:
        """Garante que o overlay sempre cubra o vídeo."""
        super().resizeEvent(event)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._empty_label.setGeometry(0, 0, self.width(), self.height())
        self._status_label.adjustSize()
        self.resized.emit(self.width(), self.height())
