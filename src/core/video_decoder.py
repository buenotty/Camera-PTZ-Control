"""FFmpeg preview fallback for VLC builds without modern RTSP support."""
import shutil
import subprocess
import threading
import time
from PySide6.QtGui import QImage


class FFmpegPreview:
    WIDTH, HEIGHT = 1280, 720

    def __init__(self, url, on_frame, on_error):
        self.url = url
        self.on_frame, self.on_error = on_frame, on_error
        self.process = None
        self.last_frame = 0.0
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def is_playing(self):
        return not self._stopped.is_set() and self._thread.is_alive() and time.monotonic() - self.last_frame < 5

    def _run(self):
        try:
            command = [shutil.which('ffmpeg'), '-hide_banner', '-loglevel', 'error',
                '-rtsp_transport', 'tcp', '-timeout', '5000000', '-i', self.url,
                '-an', '-vf', f'scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=decrease,pad={self.WIDTH}:{self.HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=25',
                '-pix_fmt', 'bgra', '-f', 'rawvideo', 'pipe:1']
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.process = process
            size = self.WIDTH * self.HEIGHT * 4
            while not self._stopped.is_set():
                data = process.stdout.read(size)
                if len(data) != size:
                    break
                frame = QImage(data, self.WIDTH, self.HEIGHT, self.WIDTH * 4, QImage.Format.Format_RGB32).copy()
                self.last_frame = time.monotonic()
                if not self._stopped.is_set():
                    self.on_frame(frame)
            if not self._stopped.is_set():
                self.on_error('Leitura RTSP interrompida. Confira a rede, a URL e as credenciais.')
        except (OSError, ValueError):
            if not self._stopped.is_set():
                self.on_error('Não foi possível iniciar a prévia com FFmpeg.')
        finally:
            if self.process:
                self._close_process()

    def _close_process(self):
        process = self.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdout:
            process.stdout.close()

    def stop(self):
        self._stopped.set()
        if self.process:
            # Do not close stdout while the reader is blocked in read().
            if self.process.poll() is None:
                self.process.terminate()
        self._thread.join(timeout=3)
