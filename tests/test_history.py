import unittest
from PySide6.QtCore import QCoreApplication
import sys

from src.core.models import ImageSettings
from src.utils.history import SettingsHistory

class TestHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication(sys.argv)
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self):
        self.history = SettingsHistory(max_states=5)

    def test_undo_redo_empty(self):
        self.assertFalse(self.history.can_undo)
        self.assertFalse(self.history.can_redo)
        self.assertIsNone(self.history.undo())
        self.assertIsNone(self.history.redo())

    def test_push_and_undo(self):
        s1 = ImageSettings(brightness=30.0)
        s2 = ImageSettings(brightness=60.0)
        self.history.push(s1)
        self.history.push(s2)

        self.assertTrue(self.history.can_undo)
        self.assertFalse(self.history.can_redo)

        restored = self.history.undo()
        self.assertIsNotNone(restored)
        self.assertEqual(restored.brightness, 30.0)

        self.assertTrue(self.history.can_redo)
        redone = self.history.redo()
        self.assertEqual(redone.brightness, 60.0)

    def test_max_states_capping(self):
        for i in range(10):
            self.history.push(ImageSettings(brightness=float(i)))
        # Stack capped at 5
        self.assertLessEqual(len(self.history._states), 5)

if __name__ == '__main__':
    unittest.main()
