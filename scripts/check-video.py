"""Read-only RTSP validation with decoded frames, PNG capture and MKV recording."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from src.ui.video_panel import VideoPanel


def wait_for(predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        QTest.qWait(30)
    raise RuntimeError('O vídeo não ficou pronto no prazo esperado.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='URL RTSP de teste; credenciais não são impressas')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    panel = VideoPanel()
    panel.resize(960, 540)
    panel.show()
    try:
        with tempfile.TemporaryDirectory(prefix='ptz-video-check-') as directory:
            root = Path(directory)
            recording = root / 'capture.mkv'
            panel.play(args.url)
            wait_for(lambda: panel.is_playing() and not panel._video_frame.frame.isNull(), 12)
            assert panel._video_frame.frame.save(str(root / 'snapshot.png'))
            panel.start_recording(str(recording))
            wait_for(panel.is_recording, 12)
            QTest.qWait(2200)
            panel.stop_recording()
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                'stream=codec_name,width,height', '-show_entries', 'format=duration', '-of', 'json', str(recording)],
                capture_output=True, check=True, text=True)
            report = json.loads(result.stdout)
            assert report['streams'] and float(report['format']['duration']) > 0
            report['qt_preview'] = [panel._video_frame.frame.width(), panel._video_frame.frame.height()]
            report['png_capture'] = (root / 'snapshot.png').stat().st_size > 0
            print(json.dumps(report, indent=2))
    finally:
        panel.shutdown()
        panel.close()


if __name__ == '__main__':
    main()
