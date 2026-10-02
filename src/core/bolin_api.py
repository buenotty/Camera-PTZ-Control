import base64
import json
import time
import requests
from typing import Optional, Dict, Any, List

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BolinAPIError(Exception):
    """Exceção customizada para erros na API da Bolin / Câmera IP."""
    pass


class BolinAPIClient:
    """
    Cliente HTTP nativo para câmeras PTZ Bolin / GXX-ISP.
    Utiliza autenticação x-www-form-urlencoded com parâmetros em Base64 e JSON,
    comunicação REST com endpoints /apiv2/video, /apiv2/ptzctrl e /apiv2/login.
    """

    def __init__(self, ip: str, port: int = 80, username: str = 'admin', password: str = ''):
        """
        Inicializa o cliente da API Bolin.

        Args:
            ip: Endereço IP da câmera.
            port: Porta HTTP da câmera (padrão: 80).
            username: Nome de usuário (padrão: admin).
            password: Senha informada pelo usuário.
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self._session = requests.Session()
        self.timeout = (2, 3)
        self.max_retries = 0
        self._cached_video_params: Dict[str, Any] = {}

    @property
    def base_url(self) -> str:
        """URL base da API calculada dinamicamente."""
        return f"http://{self.ip}:{self.port}"

    @property
    def is_connected(self) -> bool:
        """Verifica se o cliente está conectado e autenticado."""
        return self.token is not None

    def _get_auth_headers_and_body(self, payload: dict) -> tuple[dict, str]:
        """Gera os cabeçalhos e o corpo com autenticação nativa da câmera."""
        user_b64 = base64.b64encode(self.username.encode('utf-8')).decode('ascii')
        pass_b64 = base64.b64encode(self.password.encode('utf-8')).decode('ascii')
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        body = f"ReqUserName={user_b64}&ReqUserPwd={pass_b64}&{json.dumps(payload)}"
        return headers, body

    def connect(self) -> bool:
        """
        Realiza a autenticação na API testando comunicação com /apiv2/video.

        Returns:
            bool: True se conectado com sucesso.
        """
        self.token = None
        self._cached_video_params.clear()
        user_b64 = base64.b64encode(self.username.encode('utf-8')).decode('ascii')

        # Testar com ReqGetVideoParam
        payload = {
            "Cmd": "ReqGetVideoParam",
            "wCmdId": 40001089,
            "Content": {"ChanNum": 0}
        }
        headers, body = self._get_auth_headers_and_body(payload)

        try:
            response = self._session.post(
                f"{self.base_url}/apiv2/video",
                data=body,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            n_result = int(data.get("Content", {}).get("nResult", 0))

            # Se nResult == 0 ou obteve resposta com VideoParam
            if n_result == 0 and isinstance(data.get("Content", {}).get("VideoParam"), dict) and data["Content"]["VideoParam"]:
                self.token = user_b64
                self._cached_video_params = data.get("Content", {}).get("VideoParam", {})
                logger.info(f"Conectado com sucesso à API Bolin em {self.ip}")
                return True
            else:
                logger.warning(f"Resposta inesperada da API Bolin (nResult={n_result})")
                return False
        except Exception as e:
            logger.error("Falha ao conectar à API da câmera (%s)", type(e).__name__)
            return False

    def disconnect(self):
        """Desconecta limpando o token de sessão."""
        self.token = None
        self._cached_video_params.clear()
        logger.info("Desconectado da API Bolin")

    def _request(self, endpoint: str, payload: dict) -> dict:
        """
        Faz uma requisição autenticada, tentando relogin se necessário.

        Args:
            endpoint: Endpoint da API (ex: /apiv2/ptzctrl, /apiv2/video).
            payload: Dados do comando a serem enviados.

        Returns:
            dict: Resposta JSON da câmera.

        Raises:
            BolinAPIError: Se houver falha na requisição.
        """
        url = f"{self.base_url}{endpoint}"
        headers, body = self._get_auth_headers_and_body(payload)
        retries = 0

        while retries <= self.max_retries:
            try:
                response = self._session.post(url, data=body, headers=headers, timeout=self.timeout)
                if response.status_code == 401:
                    logger.warning("Token expirado, tentando reconectar...")
                    if self.connect():
                        headers, body = self._get_auth_headers_and_body(payload)
                        retries += 1
                        time.sleep(0.5)
                        continue
                    else:
                        raise BolinAPIError("Falha na reautenticação.")
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning("Falha HTTP em %s (%s)", endpoint, type(e).__name__)
                retries += 1
                if retries <= self.max_retries:
                    time.sleep(0.5 * retries)

        raise BolinAPIError(f"Falha ao realizar requisição para {endpoint} após {self.max_retries} tentativas.")

    # =========================================================================
    # Parâmetros de Vídeo e Ajustes de Imagem (ISP)
    # =========================================================================

    def get_video_param(self) -> Dict[str, Any]:
        """
        Obtém os parâmetros completos de vídeo e sensor da câmera via /apiv2/video.

        Returns:
            dict: Dicionário VideoParam com Luminance, Contrast, Saturation, Hue, etc.
        """
        payload = {
            "Cmd": "ReqGetVideoParam",
            "wCmdId": 40001089,
            "Content": {"ChanNum": 0}
        }
        resp = self._request("/apiv2/video", payload)
        content = resp.get("Content", {})
        vp = content.get("VideoParam")
        if int(content.get("nResult", 0)) != 0 or not isinstance(vp, dict) or not vp:
            raise BolinAPIError("A câmera não retornou parâmetros de imagem válidos.")
        self._cached_video_params = vp.copy()
        return vp.copy()

    def set_video_param(self, video_param: Dict[str, Any]) -> bool:
        """
        Aplica os parâmetros de vídeo na câmera via /apiv2/video.

        Args:
            video_param: Dicionário completo de VideoParam.

        Returns:
            bool: True se aplicado com sucesso.
        """
        payload = {
            "Cmd": "ReqSetVideoParam",
            "wCmdId": 40001089,
            "Content": {
                "ChanNum": 0,
                "VideoParam": video_param
            }
        }
        try:
            resp = self._request("/apiv2/video", payload)
            n_result = int(resp.get("Content", {}).get("nResult", -1))
            if n_result == 0:
                self._cached_video_params = video_param.copy()
                return True
            logger.warning(f"ReqSetVideoParam retornou erro: nResult={n_result}")
            return False
        except Exception as e:
            logger.error(f"Erro ao aplicar VideoParam: {e}")
            return False

    def update_video_param_fields(self, **kwargs) -> bool:
        """
        Atualiza campos específicos mantendo os demais inalterados.
        Exemplo: update_video_param_fields(Luminance=25, Contrast=50)
        """
        current = self.get_video_param()
        if not current:
            current = self._cached_video_params.copy()
        if not current:
            logger.error("Impossível atualizar campos: VideoParam não disponível")
            return False

        for k, v in kwargs.items():
            if k not in current:
                raise BolinAPIError(f"Campo de imagem não suportado: {k}")
            current[k] = v

        return self.set_video_param(current)

    # =========================================================================
    # Controle PTZ Nativo HTTP
    # =========================================================================

    def ptz_ctrl(self, cmd: str, param_h: int = 0, param_v: int = 0) -> bool:
        """
        Envia comando de controle PTZ nativo via /apiv2/ptzctrl.

        Args:
            cmd: Comando ('Stop', 'Left', 'Right', 'Up', 'Down', etc.)
            param_h: Velocidade ou parâmetro horizontal (0-255).
            param_v: Velocidade ou parâmetro vertical (0-255).

        Returns:
            bool: True se executado com sucesso.
        """
        payload = {
            "Cmd": "ReqPtzCtrl",
            "Content": {
                "PtzCmd": cmd,
                "ParamH": param_h,
                "ParamV": param_v
            }
        }
        try:
            resp = self._request("/apiv2/ptzctrl", payload)
            return int(resp.get("Content", {}).get("nResult", -1)) == 0
        except Exception as e:
            logger.error(f"Erro no comando PTZ HTTP '{cmd}': {e}")
            return False

    def ptz_stop(self) -> bool:
        """Comando de parada nativo HTTP fail-safe."""
        return self.ptz_ctrl("Stop", 0, 0)

    # =========================================================================
    # Presets
    # =========================================================================

    def get_presets(self) -> List[Dict[str, Any]]:
        """
        Retorna a lista real de presets salvos na câmera.
        Exemplo de retorno: [{'PresetID': 0, 'PresetName': 'CANTOR'}, ...]
        """
        payload = {
            "Cmd": "ReqGetPreset",
            "Content": {}
        }
        try:
            resp = self._request("/apiv2/ptzctrl", payload)
            return resp.get("Content", {}).get("PresetInfo", [])
        except Exception as e:
            logger.error(f"Erro ao obter presets: {e}")
            return []

    def recall_preset(self, preset_id: int) -> bool:
        """Chama um preset específico."""
        payload = {
            "Cmd": "ReqPresetCtrl",
            "Content": {
                "PresetCmd": "Call",
                "PresetID": preset_id,
                "PresetName": ""
            }
        }
        try:
            resp = self._request("/apiv2/ptzctrl", payload)
            return int(resp.get("Content", {}).get("nResult", -1)) == 0
        except Exception as e:
            logger.error(f"Erro ao chamar preset {preset_id}: {e}")
            return False

    def set_preset(self, preset_id: int, preset_name: str = "") -> bool:
        """Salva a posição atual em um preset."""
        payload = {
            "Cmd": "ReqPresetCtrl",
            "Content": {
                "PresetCmd": "Set",
                "PresetID": preset_id,
                "PresetName": preset_name
            }
        }
        try:
            resp = self._request("/apiv2/ptzctrl", payload)
            return int(resp.get("Content", {}).get("nResult", -1)) == 0
        except Exception as e:
            logger.error(f"Erro ao salvar preset {preset_id}: {e}")
            return False

    def delete_preset(self, preset_id: int) -> bool:
        """Limpa/deleta um preset na câmera."""
        payload = {
            "Cmd": "ReqPresetCtrl",
            "Content": {
                "PresetCmd": "Clean",
                "PresetID": preset_id,
                "PresetName": ""
            }
        }
        try:
            resp = self._request("/apiv2/ptzctrl", payload)
            return int(resp.get("Content", {}).get("nResult", -1)) == 0
        except Exception as e:
            logger.error(f"Erro ao deletar preset {preset_id}: {e}")
            return False

    # =========================================================================
    # CGI & Snapshot
    # =========================================================================

    def cgi_goto_preset(self, number: int):
        """Chama um preset usando a interface Fast-CGI."""
        url = f"{self.base_url}/cgi-bin/set.cgi?pelco.ptz.preset.goto={number}"
        try:
            self._session.get(url, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"Erro no CGI goto preset: {e}")

    def cgi_set_preset(self, number: int):
        """Salva um preset usando a interface Fast-CGI."""
        url = f"{self.base_url}/cgi-bin/set.cgi?pelco.ptz.preset.set={number}"
        try:
            self._session.get(url, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"Erro no CGI set preset: {e}")

    def cgi_power(self, on: bool):
        """Liga ou desliga a câmera usando a interface Fast-CGI."""
        val = 1 if on else 0
        url = f"{self.base_url}/cgi-bin/set.cgi?pelco.controller.power={val}"
        try:
            self._session.get(url, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"Erro no CGI power: {e}")

    def capture_snapshot(self, save_path: str) -> str:
        """
        Captura um snapshot JPEG da câmera.

        Args:
            save_path: Caminho para salvar a imagem.

        Returns:
            str: Caminho do arquivo salvo.
        """
        url = f"{self.base_url}/cgi-bin/snapshot.cgi"
        response = self._session.get(url, stream=True, timeout=self.timeout)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return save_path
