import math
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer, Qt

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EasingCurve(str, Enum):
    """Tipos de curvas de suavização para a movimentação."""
    LINEAR = "linear"
    EASE_IN_OUT = "ease_in_out"      # smoothstep: 3t²-2t³
    SMOOTH_STEP = "smooth_step"      # smoother step: 6t⁵-15t⁴+10t³


@dataclass
class MotionConfig:
    """Configurações da engine de movimentação suave."""
    max_ptz_speed: float = 8 / 24
    accel_time_ms: int = 300         # Tempo para alcançar velocidade máxima (ms)
    decel_time_ms: int = 200         # Tempo para parar completamente (ms)
    easing_curve: EasingCurve = EasingCurve.LINEAR
    zoom_speed_scaling: bool = False  # Auto-reduzir velocidade PTZ quando aplicado zoom
    min_speed_at_max_zoom: float = 0.15  # 15% da velocidade em zoom máximo
    max_speed_at_min_zoom: float = 1.0
    mouse_smoothing: float = 0.1     # Fator de filtro passa-baixa para o mouse (0=nenhum, 1=máximo)
    mouse_deadzone: float = 0.05     # Zona morta de 5%
    zoom_accel_time_ms: int = 250
    zoom_decel_time_ms: int = 150
    update_rate_hz: int = 30
    command_deadzone: float = 0.02   # Abaixo deste valor, considera-se zero

    def to_dict(self) -> Dict[str, Any]:
        """Converte a configuração para um dicionário para serialização."""
        data = asdict(self)
        data['easing_curve'] = self.easing_curve.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MotionConfig':
        """Cria uma configuração a partir de um dicionário."""
        if 'easing_curve' in data and isinstance(data['easing_curve'], str):
            data = dict(data)
            data['easing_curve'] = EasingCurve(data['easing_curve'])
        return cls(**data)


class MotionEngine(QObject):
    """
    Motor de movimentação suave (Motion Engine).
    Fica entre a entrada do usuário e o CameraManager, processando comandos
    para adicionar aceleração e desaceleração suaves.
    """

    # Sinais para feedback da interface
    velocity_changed = Signal(float, float)      # pan, tilt atuais
    zoom_velocity_changed = Signal(float)        # zoom atual
    speed_info_updated = Signal(float, float, float)  # pan%, tilt%, zoom% para display
    movement_started = Signal()
    movement_stopped = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Inicializa a engine e suas variáveis de estado."""
        super().__init__(parent)

        self._config = MotionConfig()
        self._ramps = {}

        # Alvos de velocidade (o que o usuário deseja)
        self._target_pan = 0.0
        self._target_tilt = 0.0
        self._target_zoom = 0.0

        # Valores suavizados atuais
        self._current_pan = 0.0
        self._current_tilt = 0.0
        self._current_zoom = 0.0

        # Filtro de mouse
        self._filtered_pan = 0.0
        self._filtered_tilt = 0.0

        # Estado atual da câmera
        self._zoom_level = 0.0  # 0.0 (wide) a 1.0 (tele)

        # Controle de estado de movimentação
        self._is_ptz_moving = False
        self._was_moving = False

        # Rastreamento da última velocidade emitida (para evitar flood de comandos repetidos)
        self._last_emitted_pan = 0.0
        self._last_emitted_tilt = 0.0
        self._last_emitted_zoom = 0.0
        self._emit_threshold = 0.03  # Só re-emitir se mudar mais que 3%

        # Timers
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._update)
        self._elapsed = QElapsedTimer()

    def set_config(self, config: MotionConfig) -> None:
        """Atualiza os parâmetros de movimentação."""
        config.update_rate_hz = max(1, min(60, config.update_rate_hz))
        config.max_ptz_speed = max(1 / 24, min(1.0, config.max_ptz_speed))
        self._config = config
        self._ramps.clear()
        logger.debug(f"Configurações de movimentação atualizadas: {config.to_dict()}")

        if self._timer.isActive():
            self._timer.setInterval(1000 // self._config.update_rate_hz)

    def start(self) -> None:
        """Inicia o loop de atualização a 30Hz."""
        if not self._timer.isActive():
            self._timer.start(1000 // self._config.update_rate_hz)
            self._elapsed.start()
            logger.info("MotionEngine iniciado.")

    def stop(self) -> None:
        """Para o loop de atualização."""
        if self._timer.isActive():
            self._timer.stop()
            self.emergency_stop()
            logger.info("MotionEngine parado.")

    def set_target_velocity(self, pan: float, tilt: float) -> None:
        """
        Define a velocidade alvo de pan e tilt [-1.0, 1.0].
        Geralmente chamado pelo teclado ao pressionar/soltar teclas.
        """
        self._target_pan = max(-1.0, min(1.0, pan))
        self._target_tilt = max(-1.0, min(1.0, tilt))

    def set_mouse_velocity(self, raw_pan: float, raw_tilt: float) -> None:
        """
        Define a velocidade a partir do mouse, aplicando um filtro passa-baixa
        e zona morta.
        """
        alpha = 1.0 - self._config.mouse_smoothing
        self._filtered_pan = alpha * raw_pan + (1 - alpha) * self._filtered_pan
        self._filtered_tilt = alpha * raw_tilt + (1 - alpha) * self._filtered_tilt

        # Aplica a zona morta
        pan_val = self._filtered_pan if abs(self._filtered_pan) >= self._config.mouse_deadzone else 0.0
        tilt_val = self._filtered_tilt if abs(self._filtered_tilt) >= self._config.mouse_deadzone else 0.0

        self.set_target_velocity(pan_val, tilt_val)

    def set_target_zoom(self, zoom: float) -> None:
        """Define a velocidade alvo do zoom [-1.0, 1.0]."""
        self._target_zoom = max(-1.0, min(1.0, zoom))

    def set_zoom_level(self, level: float) -> None:
        """
        Informa o nível atual de zoom reportado pela câmera [0.0=wide, 1.0=tele].
        Utilizado para auto-escala da velocidade.
        """
        self._zoom_level = max(0.0, min(1.0, level))

    def emergency_stop(self) -> None:
        """Para todos os movimentos imediatamente, ignorando desaceleração."""
        self._ramps.clear()
        self._target_pan = 0.0
        self._target_tilt = 0.0
        self._target_zoom = 0.0

        self._current_pan = 0.0
        self._current_tilt = 0.0
        self._current_zoom = 0.0

        self._filtered_pan = 0.0
        self._filtered_tilt = 0.0

        self._is_ptz_moving = False
        self._was_moving = False

        self._last_emitted_pan = 0.0
        self._last_emitted_tilt = 0.0
        self._last_emitted_zoom = 0.0

        self.velocity_changed.emit(0.0, 0.0)
        self.zoom_velocity_changed.emit(0.0)
        self.speed_info_updated.emit(0.0, 0.0, 0.0)
        self.movement_stopped.emit()

    def _interpolate_axis(self, current: float, target: float, dt: float,
                          is_accelerating: bool,
                          accel_time: Optional[float] = None,
                          decel_time: Optional[float] = None) -> float:
        """
        Realiza a interpolação central entre o valor atual e o alvo, aplicando curvas
        de suavização conforme a configuração.
        """
        if accel_time is None:
            accel_time = self._config.accel_time_ms / 1000.0
        if decel_time is None:
            decel_time = self._config.decel_time_ms / 1000.0

        ramp_time = accel_time if is_accelerating else decel_time
        if ramp_time <= 0.0:
            return target

        # Taxa de mudança por segundo (velocidade da rampa)
        max_delta = dt / ramp_time

        diff = target - current
        if abs(diff) < 0.001:
            return target

        # Limita o tamanho do passo (step)
        step = max(-max_delta, min(max_delta, diff))
        new_value = current + step

        return new_value

    def _ramp_axis(self, axis: str, current: float, target: float, dt: float,
                   accel_ms: int, decel_ms: int) -> float:
        # Easing is evaluated from a fixed origin; re-easing the previous
        # result can stall indefinitely at high zoom or jump on reversal.
        ramp = self._ramps.get(axis)
        if ramp is None or ramp[1] != target:
            duration = (accel_ms if abs(target) > abs(current) else decel_ms) / 1000
            ramp = [current, target, 0.0, duration]
            self._ramps[axis] = ramp
        ramp[2] += dt
        t = min(1.0, ramp[2] / ramp[3]) if ramp[3] > 0 else 1.0
        if self._config.easing_curve == EasingCurve.EASE_IN_OUT:
            t = t * t * (3 - 2 * t)
        elif self._config.easing_curve == EasingCurve.SMOOTH_STEP:
            t = t ** 3 * (10 - 15 * t + 6 * t * t)
        return ramp[0] + (target - ramp[0]) * t

    def _calculate_zoom_scale(self) -> float:
        """
        Calcula o fator de escala de velocidade baseado no nível atual de zoom.
        Usa interpolação logarítmica pois o zoom é percebido de forma não-linear.
        """
        min_s = self._config.min_speed_at_max_zoom
        max_s = self._config.max_speed_at_min_zoom

        if self._zoom_level <= 0.0:
            return max_s
        if self._zoom_level >= 1.0:
            return min_s

        return max_s * ((min_s / max_s) ** self._zoom_level)

    def _update(self) -> None:
        """O loop central que roda a 30Hz e recalcula as velocidades interpoladas."""
        dt = self._elapsed.restart() / 1000.0  # tempo decorrido em segundos

        dt = max(0.0, min(dt, 0.1))
        for axis in ('pan', 'tilt', 'zoom'):
            is_zoom = axis == 'zoom'
            value = self._ramp_axis(
                axis, getattr(self, '_current_' + axis), getattr(self, '_target_' + axis), dt,
                self._config.zoom_accel_time_ms if is_zoom else self._config.accel_time_ms,
                self._config.zoom_decel_time_ms if is_zoom else self._config.decel_time_ms,
            )
            setattr(self, '_current_' + axis, value)

        # Escala da velocidade dependendo do zoom (se ativado)
        scale = self._calculate_zoom_scale() if self._config.zoom_speed_scaling else 1.0
        pan_out = self._current_pan * scale * self._config.max_ptz_speed
        tilt_out = self._current_tilt * scale * self._config.max_ptz_speed

        # Verifica se o movimento efetivamente parou (deadzone)
        pan_stopped = abs(pan_out) < self._config.command_deadzone
        tilt_stopped = abs(tilt_out) < self._config.command_deadzone
        zoom_stopped = abs(self._current_zoom) < self._config.command_deadzone

        pan_out = 0.0 if pan_stopped else pan_out
        tilt_out = 0.0 if tilt_stopped else tilt_out
        if pan_stopped and tilt_stopped:
            if self._is_ptz_moving:
                self._is_ptz_moving = False
                pan_out = 0.0
                tilt_out = 0.0
        else:
            if not self._is_ptz_moving:
                self._is_ptz_moving = True
                self.movement_started.emit()

        # Só emite velocity_changed se a velocidade mudou significativamente
        # (evita inundar a câmera com comandos VISCA idênticos a 30Hz)
        pan_changed = abs(pan_out - self._last_emitted_pan) > self._emit_threshold
        tilt_changed = abs(tilt_out - self._last_emitted_tilt) > self._emit_threshold
        pan_changed |= pan_out * self._last_emitted_pan < 0 or (pan_out == 0) != (self._last_emitted_pan == 0)
        tilt_changed |= tilt_out * self._last_emitted_tilt < 0 or (tilt_out == 0) != (self._last_emitted_tilt == 0)
        # Sempre emitir transição para/de zero (start/stop é crítico)
        going_to_zero = (pan_stopped and tilt_stopped and self._is_ptz_moving == False
                         and (self._last_emitted_pan != 0.0 or self._last_emitted_tilt != 0.0))
        leaving_zero = (not pan_stopped or not tilt_stopped) and self._last_emitted_pan == 0.0 and self._last_emitted_tilt == 0.0

        if pan_changed or tilt_changed or going_to_zero or leaving_zero:
            self.velocity_changed.emit(pan_out, tilt_out)
            self._last_emitted_pan = pan_out
            self._last_emitted_tilt = tilt_out

        # Zoom: só emitir se mudou
        zoom_out_val = self._current_zoom if not zoom_stopped else 0.0
        if abs(zoom_out_val - self._last_emitted_zoom) > self._emit_threshold or (zoom_stopped and self._last_emitted_zoom != 0.0):
            self.zoom_velocity_changed.emit(zoom_out_val)
            self._last_emitted_zoom = zoom_out_val

        # Atualiza a interface sobre os percentuais de velocidade (UI pode receber a 30Hz sem problema)
        self.speed_info_updated.emit(
            abs(pan_out) * 100.0,
            abs(tilt_out) * 100.0,
            abs(self._current_zoom) * 100.0
        )

        # Avisa que todo o movimento (pan/tilt e zoom) parou
        if pan_stopped and tilt_stopped and zoom_stopped and self._was_moving:
            self.movement_stopped.emit()

        self._was_moving = self._is_ptz_moving or not zoom_stopped
