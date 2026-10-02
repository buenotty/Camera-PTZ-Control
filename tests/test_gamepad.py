from types import SimpleNamespace
from unittest.mock import Mock
from src.input.gamepad_handler import GamepadHandler
from src.core.motion_engine import MotionEngine


def controller_fixture():
    state = {'axes': [0, 0, 0, 0], 'button': 0, 'count': 1, 'active': True}
    device = Mock()
    device.get_numaxes.return_value = 4
    device.get_numbuttons.return_value = 1
    device.get_name.return_value = 'Test gamepad'
    device.get_axis.side_effect = lambda index: state['axes'][index]
    device.get_button.side_effect = lambda index: state['button']
    backend = SimpleNamespace(event=SimpleNamespace(pump=lambda: None),
        joystick=SimpleNamespace(get_count=lambda: state['count'], Joystick=lambda index: device))
    engine = MotionEngine()
    handler = GamepadHandler(engine, active=lambda: state['active'], backend=backend)
    handler.set_enabled(True)
    return state, engine, handler


def test_controller_requires_neutral_after_emergency():
    state, engine, handler = controller_fixture()
    try:
        state['axes'][0] = 1
        handler.poll()
        assert engine._target_pan == 0
        state['axes'][0] = 0
        handler.poll()
        assert handler.armed
        state['axes'] = [1, -1, 0, -1]
        handler.poll()
        assert (engine._target_pan, engine._target_tilt, engine._target_zoom) == (1, 1, 1)
        state['button'] = 1
        handler.poll()
        assert (engine._target_pan, engine._target_zoom) == (0, 0)
        state['button'] = 0
        handler.poll()
        assert not handler.armed
        assert engine._target_pan == 0
        state['axes'] = [0, 0, 0, 0]
        handler.poll()
        assert handler.armed
    finally:
        handler.shutdown()


def test_controller_stops_on_focus_loss_or_device_removal():
    state, engine, handler = controller_fixture()
    try:
        handler.poll()
        state['axes'][0] = 1
        handler.poll()
        state['active'] = False
        handler.poll()
        assert engine._target_pan == 0
        assert not handler.armed
        state['active'] = True
        state['axes'][0] = 0
        handler.poll()
        state['axes'][0] = 1
        handler.poll()
        state['count'] = 0
        handler.poll()
        assert engine._target_pan == 0
        assert handler.joystick is None
    finally:
        handler.shutdown()
