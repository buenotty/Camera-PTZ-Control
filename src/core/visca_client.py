import socket
import struct
import threading
import time
from typing import Tuple

from src.utils.logger import get_logger


class VISCAClient:
    """
    Cliente VISCA over IP para controle de câmeras PTZ.

    Gerencia a comunicação UDP na porta especificada e implementa os comandos
    VISCA para movimento Pan/Tilt/Zoom, foco, exposição e presets.
    """

    def __init__(self, ip: str, port: int = 52381):
        """
        Inicializa o cliente VISCA.

        Args:
            ip: Endereço IP da câmera.
            port: Porta UDP para comunicação (padrão 52381).
        """
        self.ip = ip
        self.port = port
        self.logger = get_logger(__name__)

        self._socket = None
        self._is_running = False
        self._receive_thread = None

        self._sequence_number = 1
        self._seq_lock = threading.Lock()

        self._inquiry_lock = threading.Lock()
        self._inquiry_event = threading.Event()
        self._inquiry_response = b''
        self._inquiry_sequence = None

    @property
    def is_connected(self) -> bool:
        """Retorna True se o socket estiver criado e o loop de recepção ativo."""
        return self._socket is not None and self._is_running

    def connect(self):
        """Configura o socket UDP e inicia a thread de recepção."""
        if self.is_connected:
            return True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.settimeout(0.5)  # Timeout curto para permitir o fechamento suave da thread
            self._is_running = True

            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()
            self.logger.info(f"Conectado à câmera VISCA em {self.ip}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao conectar ao VISCA: {e}")
            self.disconnect()
            return False


    def disconnect(self):
        """Fecha o socket e encerra a thread de recepção."""
        self._is_running = False
        if self._receive_thread and self._receive_thread.is_alive():
            self._receive_thread.join(timeout=1.0)

        if self._socket:
            self._socket.close()
            self._socket = None

        self.logger.info("Desconectado da câmera VISCA.")

    def _create_header(self, payload: bytes, is_inquiry: bool = False) -> bytes:
        """Gera o cabeçalho de 8 bytes VISCA-over-IP."""
        msg_type = b'\x01\x10' if is_inquiry else b'\x01\x00'
        length = len(payload)
        with self._seq_lock:
            seq = self._sequence_number
            self._sequence_number = (self._sequence_number + 1) & 0xFFFFFFFF
        return msg_type + struct.pack('>H', length) + struct.pack('>I', seq)

    def _get_direction_bytes(self, direction: str) -> tuple[int, int]:
        """Retorna os bytes de direção VISCA para a direção indicada."""
        directions = {
            'Up': (0x03, 0x01),
            'Down': (0x03, 0x02),
            'Left': (0x01, 0x03),
            'Right': (0x02, 0x03),
            'UpLeft': (0x01, 0x01),
            'UpRight': (0x02, 0x01),
            'DownLeft': (0x01, 0x02),
            'DownRight': (0x02, 0x02),
            'Stop': (0x03, 0x03)
        }
        return directions.get(direction, (0x03, 0x03))

    def _send(self, payload: bytes, is_inquiry: bool = False):
        """
        Envelopa o comando VISCA no cabeçalho VISCA-over-IP e envia.

        Args:
            payload: O comando VISCA propriamente dito.
            is_inquiry: True se for uma mensagem de consulta (inquiry).
        """
        if not self.is_connected:
            self.logger.warning("Tentativa de envio sem estar conectado.")
            return

        header = self._create_header(payload, is_inquiry)
        packet = header + payload
        if is_inquiry:
            self._inquiry_sequence = int.from_bytes(header[4:8], "big")

        try:
            self._socket.sendto(packet, (self.ip, self.port))
            # self.logger.debug(f"Enviado: {packet.hex()}")
        except Exception as e:
            self.logger.error(f"Erro ao enviar pacote VISCA: {e}")

    def _receive_loop(self):
        """Thread em background escutando respostas e ACKs da câmera."""
        while self._is_running:
            try:
                data, source = self._socket.recvfrom(1024)
                if source != (self.ip, self.port):
                    continue
                if len(data) >= 8 and int.from_bytes(data[2:4], "big") == len(data) - 8:
                    payload = data[8:]
                    if not payload:
                        continue

                    # Verifica se é uma resposta da câmera (inicia com 0x90)
                    if len(payload) >= 3 and payload[0] == 0x90 and payload[-1] == 0xFF:
                        # 0x50 indica Completion (Conclusão)
                        # Comandos normais de completion têm 3 bytes (90 5y FF).
                        # Inquiries de completion têm mais de 3 bytes (90 5y data... FF).
                        if ((payload[1] & 0xF0) == 0x50 and len(payload) > 3
                                and int.from_bytes(data[4:8], "big") == self._inquiry_sequence):
                            if not self._inquiry_event.is_set():
                                self._inquiry_response = payload
                                self._inquiry_event.set()
            except socket.timeout:
                continue
            except Exception as e:
                if self._is_running:
                    self.logger.error(f"Erro no loop de recepção VISCA: {e}")

    def _inquiry(self, payload: bytes, timeout: float = 2.0) -> bytes:
        """
        Envia uma consulta e aguarda a resposta com timeout.

        Args:
            payload: Comando VISCA de consulta.
            timeout: Tempo máximo de espera pela resposta.

        Returns:
            Os bytes da resposta VISCA (excluindo cabeçalho IP), ou b'' em caso de erro/timeout.
        """
        with self._inquiry_lock:
            self._inquiry_event.clear()
            self._inquiry_response = b''
            self._send(payload, is_inquiry=True)

            if self._inquiry_event.wait(timeout):
                return self._inquiry_response
            else:
                self.logger.warning("Timeout aguardando resposta de inquiry VISCA.")
                return b''

    def _value_to_nibbles(self, value: int, count: int = 4) -> bytes:
        """Converte um número inteiro para o formato de nibbles VISCA."""
        # Limita ao valor máximo para o número de nibbles solicitado
        max_val = (1 << (count * 4)) - 1
        val = max(0, min(value, max_val))

        hex_str = f"{val:0{count}X}"
        return bytes(int(char, 16) for char in hex_str)

    def _nibbles_to_value(self, data: bytes) -> int:
        """Converte dados em formato de nibbles VISCA para inteiro."""
        val = 0
        for byte in data:
            val = (val << 4) | (byte & 0x0F)
        return val

    # =========================================================================
    # Movimento Pan/Tilt
    # =========================================================================

    def pan_tilt(self, pan_speed: int, tilt_speed: int, direction: str):
        """
        Movimento contínuo de Pan/Tilt.

        Args:
            pan_speed: Velocidade de pan (1 a 24).
            tilt_speed: Velocidade de tilt (1 a 24).
            direction: Direção do movimento ('Up', 'Down', 'Left', 'Right',
                       'UpLeft', 'UpRight', 'DownLeft', 'DownRight', 'Stop').
        """
        directions = {
            'Up': (0x03, 0x01),
            'Down': (0x03, 0x02),
            'Left': (0x01, 0x03),
            'Right': (0x02, 0x03),
            'UpLeft': (0x01, 0x01),
            'UpRight': (0x02, 0x01),
            'DownLeft': (0x01, 0x02),
            'DownRight': (0x02, 0x02),
            'Stop': (0x03, 0x03)
        }

        if direction not in directions:
            raise ValueError(f"Direção VISCA inválida: {direction}")
        dir_bytes = directions[direction]
        p_speed = max(1, min(24, pan_speed))
        t_speed = max(1, min(20, tilt_speed))

        payload = bytes([0x81, 0x01, 0x06, 0x01, p_speed, t_speed, dir_bytes[0], dir_bytes[1], 0xFF])
        self._send(payload)

    def pan_tilt_absolute(self, pan: int, tilt: int, pan_speed: int, tilt_speed: int):
        """Move para uma posição absoluta de Pan/Tilt."""
        p_speed = max(1, min(24, pan_speed))
        t_speed = max(1, min(20, tilt_speed))

        pan_nibbles = self._value_to_nibbles(pan, 4)
        tilt_nibbles = self._value_to_nibbles(tilt, 4)

        payload = bytes([0x81, 0x01, 0x06, 0x02, p_speed, t_speed]) + pan_nibbles + tilt_nibbles + b'\xFF'
        self._send(payload)

    def stop(self):
        """Para todos os movimentos contínuos de Pan/Tilt."""
        self.pan_tilt(1, 1, 'Stop')

    def home(self):
        """Move a câmera para a posição Home."""
        self._send(b'\x81\x01\x06\x04\xFF')

    # =========================================================================
    # Zoom
    # =========================================================================

    def zoom_tele(self, speed: int = 0):
        """Aproxima o zoom (Tele)."""
        if speed == 0:
            self._send(b'\x81\x01\x04\x07\x02\xFF')
        else:
            p = max(0, min(7, speed))
            self._send(bytes([0x81, 0x01, 0x04, 0x07, 0x20 | p, 0xFF]))

    def zoom_wide(self, speed: int = 0):
        """Afasta o zoom (Wide)."""
        if speed == 0:
            self._send(b'\x81\x01\x04\x07\x03\xFF')
        else:
            p = max(0, min(7, speed))
            self._send(bytes([0x81, 0x01, 0x04, 0x07, 0x30 | p, 0xFF]))

    def zoom_stop(self):
        """Para o movimento de zoom."""
        self._send(b'\x81\x01\x04\x07\x00\xFF')

    def zoom_absolute(self, position: int):
        """Move o zoom para uma posição absoluta."""
        nibbles = self._value_to_nibbles(position, 4)
        payload = bytes([0x81, 0x01, 0x04, 0x47]) + nibbles + b'\xFF'
        self._send(payload)

    # =========================================================================
    # Focus
    # =========================================================================

    def focus_auto(self):
        """Ativa o foco automático."""
        self._send(b'\x81\x01\x04\x38\x02\xFF')

    def focus_manual(self):
        """Ativa o foco manual."""
        self._send(b'\x81\x01\x04\x38\x03\xFF')

    def focus_far(self):
        """Move o foco para longe."""
        self._send(b'\x81\x01\x04\x08\x02\xFF')

    def focus_near(self):
        """Move o foco para perto."""
        self._send(b'\x81\x01\x04\x08\x03\xFF')

    def focus_stop(self):
        """Para o movimento de foco."""
        self._send(b'\x81\x01\x04\x08\x00\xFF')

    def focus_one_push(self):
        """Realiza um ajuste de foco instantâneo (One Push Trigger)."""
        self._send(b'\x81\x01\x04\x18\x01\xFF')

    # =========================================================================
    # Imagem e Exposição
    # =========================================================================

    def set_exposure_mode(self, mode: str):
        """Define o modo de exposição (Auto, Manual, ShutterPriority, IrisPriority)."""
        modes = {
            'Auto': 0x00,
            'Manual': 0x03,
            'ShutterPriority': 0x0A,
            'IrisPriority': 0x0B
        }
        val = modes.get(mode)
        if val is not None:
            self._send(bytes([0x81, 0x01, 0x04, 0x39, val, 0xFF]))

    def set_brightness(self, value: int):
        """Define o brilho."""
        val = max(0, min(0x17, value))
        p = (val >> 4) & 0x0F
        q = val & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x4D, 0x00, 0x00, p, q, 0xFF]))

    def set_iris(self, value: int):
        """Define a abertura da íris."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x4B, 0x00, 0x00, p, q, 0xFF]))

    def set_gain(self, value: int):
        """Define o ganho."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x4C, 0x00, 0x00, p, q, 0xFF]))

    def set_shutter_speed(self, value: int):
        """Define a velocidade do obturador (shutter)."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x4A, 0x00, 0x00, p, q, 0xFF]))

    def set_white_balance_mode(self, mode: str):
        """Define o modo de balanço de branco."""
        modes = {
            'Auto': 0x00,
            'Indoor': 0x01,
            'Outdoor': 0x02,
            'OnePush': 0x03,
            'Manual': 0x05
        }
        val = modes.get(mode)
        if val is not None:
            self._send(bytes([0x81, 0x01, 0x04, 0x35, val, 0xFF]))

    def set_red_gain(self, value: int):
        """Define o ganho de vermelho (Manual White Balance)."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x43, 0x00, 0x00, p, q, 0xFF]))

    def set_blue_gain(self, value: int):
        """Define o ganho de azul (Manual White Balance)."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x44, 0x00, 0x00, p, q, 0xFF]))

    def set_exposure_compensation(self, enabled: bool):
        """Ativa/Desativa compensação de exposição."""
        val = 0x02 if enabled else 0x03
        self._send(bytes([0x81, 0x01, 0x04, 0x3E, val, 0xFF]))

    def set_exposure_compensation_value(self, value: int):
        """Define o valor da compensação de exposição."""
        p = (value >> 4) & 0x0F
        q = value & 0x0F
        self._send(bytes([0x81, 0x01, 0x04, 0x4E, 0x00, 0x00, p, q, 0xFF]))

    # =========================================================================
    # Consultas (Inquiries)
    # =========================================================================

    def get_pan_tilt_position(self) -> Tuple[int, int]:
        """Obtém a posição atual de Pan e Tilt."""
        resp = self._inquiry(b'\x81\x09\x06\x12\xFF')
        if len(resp) >= 11:
            pan = self._nibbles_to_value(resp[2:6])
            tilt = self._nibbles_to_value(resp[6:10])

            # Tratamento de inteiros com sinal (16 bits)
            if pan > 0x7FFF:
                pan -= 0x10000
            if tilt > 0x7FFF:
                tilt -= 0x10000

            return pan, tilt
        return 0, 0

    def get_zoom_position(self, timeout: float = 0.5):
        """Obtém a posição atual do Zoom."""
        resp = self._inquiry(b'\x81\x09\x04\x47\xFF', timeout=timeout)
        if len(resp) >= 7:
            return self._nibbles_to_value(resp[2:6])
        return None

    def get_exposure_mode(self) -> str:
        """Obtém o modo atual de exposição."""
        resp = self._inquiry(b'\x81\x09\x04\x39\xFF')
        if len(resp) >= 4:
            val = resp[2]
            modes = {
                0x00: 'Auto',
                0x03: 'Manual',
                0x0A: 'ShutterPriority',
                0x0B: 'IrisPriority'
            }
            return modes.get(val, 'Unknown')
        return 'Unknown'

    def get_white_balance_mode(self) -> str:
        """Obtém o modo atual de balanço de branco."""
        resp = self._inquiry(b'\x81\x09\x04\x35\xFF')
        if len(resp) >= 4:
            val = resp[2]
            modes = {
                0x00: 'Auto',
                0x01: 'Indoor',
                0x02: 'Outdoor',
                0x03: 'OnePush',
                0x05: 'Manual'
            }
            return modes.get(val, 'Unknown')
        return 'Unknown'

    # =========================================================================
    # Presets
    # =========================================================================

    def recall_preset(self, number: int):
        """Chama um preset previamente salvo."""
        num = max(0, min(255, number))
        self._send(bytes([0x81, 0x01, 0x04, 0x3F, 0x02, num, 0xFF]))

    def set_preset(self, number: int):
        """Salva a posição atual num preset."""
        num = max(0, min(255, number))
        self._send(bytes([0x81, 0x01, 0x04, 0x3F, 0x01, num, 0xFF]))

    def clear_preset(self, number: int):
        """Limpa (remove) um preset salvo."""
        num = max(0, min(255, number))
        self._send(bytes([0x81, 0x01, 0x04, 0x3F, 0x00, num, 0xFF]))
