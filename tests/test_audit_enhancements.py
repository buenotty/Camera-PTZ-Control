import unittest
import sys
import time
from PySide6.QtCore import QCoreApplication, Qt, QPointF
from PySide6.QtGui import QKeyEvent, QWheelEvent

from src.core.models import ImageSettings, ExposureMode, WhiteBalanceMode
from src.core.bolin_api import BolinAPIClient
from src.input.keyboard_handler import KeyboardHandler
from src.ui.image_settings import ImageSettingsPanel, NoWheelSpinBox, _NumericSettingRow


class TestAuditEnhancements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_bolin_auth_payload_formatting(self):
        """Verifica se o cabeçalho e payload de autenticação nativa da câmera são gerados corretamente."""
        client = BolinAPIClient("192.0.2.1", username="admin", password="admin")
        headers, body = client._get_auth_headers_and_body({"Cmd": "Test"})

        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded;charset=utf-8")
        self.assertIn("ReqUserName=YWRtaW4=", body)
        self.assertIn("ReqUserPwd=YWRtaW4=", body)
        self.assertIn('"Cmd": "Test"', body)

    def test_held_key_survives_os_repeat_delay_and_release_stops(self):
        """A held key must not expire before the OS starts sending repeats."""
        from PySide6.QtTest import QTest
        from src.core.motion_engine import MotionEngine
        handler = KeyboardHandler()
        engine = MotionEngine()
        handler.set_motion_engine(engine)
        press = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(handler.handle_key_press(press))
        QTest.qWait(450)
        self.assertIn(Qt.Key.Key_Right, handler._pressed_keys)
        self.assertEqual(engine._target_pan, 1.0)
        release = QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(handler.handle_key_release(release))
        self.assertEqual(engine._target_pan, 0.0)
        self.assertNotIn(Qt.Key.Key_Right, handler._pressed_keys)

    def test_keyboard_clear_all_keys(self):
        """Verifica se clear_all_keys limpa todas as direções imediatamente."""
        handler = KeyboardHandler()
        evt1 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier)
        evt2 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier)
        handler.handle_key_press(evt1)
        handler.handle_key_press(evt2)

        self.assertEqual(len(handler._pressed_keys), 2)

        handler.clear_all_keys()
        self.assertEqual(len(handler._pressed_keys), 0)

    def test_no_wheel_spinbox_ignores_wheel(self):
        """Verifica se NoWheelSpinBox ignora o evento da roda do mouse."""
        from PySide6.QtCore import QPoint
        spin = NoWheelSpinBox()
        spin.setValue(50)

        # Simular evento de roda
        wheel_evt = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10),
            QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        spin.wheelEvent(wheel_evt)
        self.assertFalse(wheel_evt.isAccepted())
        self.assertEqual(spin.value(), 50)

    def test_image_settings_panel_has_no_sliders(self):
        """Garante que nenhum QSlider está presente no painel de imagem (conforme solicitado pelo usuário)."""
        from PySide6.QtWidgets import QSlider
        panel = ImageSettingsPanel()
        sliders = panel.findChildren(QSlider)
        self.assertEqual(len(sliders), 0, "Nenhum QSlider deve estar presente no ImageSettingsPanel!")

    def test_image_settings_roundtrip(self):
        """Verifica atualização de campos de ImageSettings a partir de objeto e exportação."""
        panel = ImageSettingsPanel()
        settings = ImageSettings(
            brightness=22.0,
            contrast=48.0,
            saturation=45.0,
            hue=52.0,
            sharpness=44.0,
            exposure_mode=ExposureMode.MANUAL,
            white_balance_mode=WhiteBalanceMode.INDOOR,
            iris=12,
            gain=5,
            shutter_speed=9,
            flip=True,
            mirror=False
        )
        panel.update_from_settings(settings)

        self.assertEqual(panel.row_brightness.value(), 22)
        self.assertEqual(panel.row_contrast.value(), 48)
        self.assertEqual(panel.row_saturation.value(), 45)
        self.assertEqual(panel.row_hue.value(), 52)
        self.assertEqual(panel.row_sharpness.value(), 44)
        self.assertEqual(panel.row_iris.value(), 12)
        self.assertEqual(panel.row_gain.value(), 5)
        self.assertEqual(panel.row_shutter.value(), 9)
        self.assertTrue(panel.chk_flip.isChecked())
        self.assertFalse(panel.chk_mirror.isChecked())


if __name__ == '__main__':
    unittest.main()
