import os
import tempfile
from pathlib import Path
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# Never modify the developer's actual profiles while running tests.
_test_data = tempfile.TemporaryDirectory(prefix='ptz-tests-')
os.environ['APPDATA'] = _test_data.name
os.environ['XDG_CONFIG_HOME'] = _test_data.name
os.environ['XDG_CACHE_HOME'] = _test_data.name
os.environ['NO_PROXY'] = '127.0.0.1,localhost'

@pytest.fixture(scope='session', autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
