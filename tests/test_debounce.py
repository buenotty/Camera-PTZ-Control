import unittest
from PySide6.QtCore import QCoreApplication, QTimer
import sys
from src.utils.debounce import Debounce, Throttle

class TestDebounceThrottle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication(sys.argv)
        else:
            cls.app = QCoreApplication.instance()

    def test_debounce_call(self):
        called = []
        d = Debounce(50, lambda x: called.append(x))
        d.call(1)
        d.call(2)
        d.call(3)
        # Should only execute after timer
        self.assertEqual(len(called), 0)

    def test_throttle_call(self):
        called = []
        t = Throttle(100, lambda x: called.append(x))
        t.call(1)
        # First call executes immediately
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0], 1)

if __name__ == '__main__':
    unittest.main()
