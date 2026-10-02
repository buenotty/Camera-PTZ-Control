import unittest
import math
from PySide6.QtCore import QCoreApplication
import sys

from src.core.motion_engine import MotionEngine, MotionConfig, EasingCurve

class TestMotionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication(sys.argv)
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self):
        self.engine = MotionEngine()

    def tearDown(self):
        self.engine.stop()

    def test_initial_state(self):
        self.assertEqual(self.engine._target_pan, 0.0)
        self.assertEqual(self.engine._target_tilt, 0.0)
        self.assertEqual(self.engine._current_pan, 0.0)
        self.assertEqual(self.engine._current_tilt, 0.0)

    def test_target_velocity_clamping(self):
        self.engine.set_target_velocity(2.5, -3.0)
        self.assertEqual(self.engine._target_pan, 1.0)
        self.assertEqual(self.engine._target_tilt, -1.0)

    def test_emergency_stop(self):
        self.engine.set_target_velocity(1.0, 1.0)
        self.engine._current_pan = 0.8
        self.engine._current_tilt = 0.8
        self.engine.emergency_stop()
        self.assertEqual(self.engine._target_pan, 0.0)
        self.assertEqual(self.engine._target_tilt, 0.0)
        self.assertEqual(self.engine._current_pan, 0.0)
        self.assertEqual(self.engine._current_tilt, 0.0)

    def test_zoom_scaling(self):
        self.engine.set_zoom_level(0.0)
        scale_wide = self.engine._calculate_zoom_scale()
        self.assertAlmostEqual(scale_wide, 1.0, places=2)

        self.engine.set_zoom_level(1.0)
        scale_tele = self.engine._calculate_zoom_scale()
        self.assertAlmostEqual(scale_tele, 0.15, places=2)

        # Tele must be significantly slower than wide to avoid jerky jumps
        self.assertLess(scale_tele, scale_wide)

    def test_easing_curve_smoothstep(self):
        val_start = self.engine._interpolate_axis(0.0, 1.0, 0.05, is_accelerating=True)
        self.assertGreater(val_start, 0.0)
        self.assertLess(val_start, 1.0)

if __name__ == '__main__':
    unittest.main()
