from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
import json
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

class ExposureMode(Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    SHUTTER_PRIORITY = "SHUTTER_PRIORITY"
    IRIS_PRIORITY = "IRIS_PRIORITY"

class WhiteBalanceMode(Enum):
    AUTO = "AUTO"
    INDOOR = "INDOOR"
    OUTDOOR = "OUTDOOR"
    MANUAL = "MANUAL"
    ONE_PUSH = "ONE_PUSH"

class InputMode(Enum):
    KEYBOARD = "KEYBOARD"
    MOUSE = "MOUSE"
    HYBRID = "HYBRID"

class PTZDirection(Enum):
    UP = "Up"
    DOWN = "Down"
    LEFT = "Left"
    RIGHT = "Right"
    UP_LEFT = "UpLeft"
    UP_RIGHT = "UpRight"
    DOWN_LEFT = "DownLeft"
    DOWN_RIGHT = "DownRight"
    STOP = "Stop"

@dataclass
class CameraConfig:
    name: str = "Câmera PTZ"
    ip: str = ""
    http_port: int = 80
    visca_port: int = 52381
    rtsp_port: int = 554
    username: str = "admin"
    password: str = ""
    rtsp_url: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.ip}:{self.http_port}"

    @property
    def stream_url(self) -> str:
        if self.rtsp_url:
            return self.rtsp_url
        credentials = f"{quote(self.username, safe='')}:{quote(self.password, safe='')}@" if self.username else ""
        return f"rtsp://{credentials}{self.ip}:{self.rtsp_port}/media/video1"

    @property
    def public_rtsp_url(self) -> str:
        if not self.rtsp_url:
            return ""
        parts = urlsplit(self.rtsp_url)
        return urlunsplit(parts._replace(netloc=parts.netloc.rsplit('@', 1)[-1]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ip": self.ip,
            "http_port": self.http_port,
            "visca_port": self.visca_port,
            "rtsp_port": self.rtsp_port,
            "username": self.username,
            "password": "",
            "rtsp_url": self.public_rtsp_url
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CameraConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class ImageSettings:
    brightness: float = 50.0
    contrast: float = 50.0
    saturation: float = 50.0
    sharpness: float = 50.0
    hue: float = 50.0
    exposure_mode: ExposureMode = ExposureMode.AUTO
    white_balance_mode: WhiteBalanceMode = WhiteBalanceMode.AUTO
    gain: int = 0
    iris: int = 0
    shutter_speed: int = 0
    red_gain: int = 128
    blue_gain: int = 128
    exposure_compensation: bool = False
    exposure_compensation_value: int = 0
    blc: bool = False
    wdr: bool = False
    noise_reduction: int = 0
    flip: bool = False
    mirror: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "sharpness": self.sharpness,
            "hue": self.hue,
            "exposure_mode": self.exposure_mode.value,
            "white_balance_mode": self.white_balance_mode.value,
            "gain": self.gain,
            "iris": self.iris,
            "shutter_speed": self.shutter_speed,
            "red_gain": self.red_gain,
            "blue_gain": self.blue_gain,
            "exposure_compensation": self.exposure_compensation,
            "exposure_compensation_value": self.exposure_compensation_value,
            "blc": self.blc,
            "wdr": self.wdr,
            "noise_reduction": self.noise_reduction,
            "flip": self.flip,
            "mirror": self.mirror
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ImageSettings':
        kwargs = {}
        for k, v in data.items():
            if k not in cls.__dataclass_fields__:
                continue
            if k == "exposure_mode" and isinstance(v, str):
                kwargs[k] = ExposureMode(v)
            elif k == "white_balance_mode" and isinstance(v, str):
                kwargs[k] = WhiteBalanceMode(v)
            else:
                kwargs[k] = v
        return cls(**kwargs)

@dataclass
class Preset:
    number: int
    name: str = ""
    thumbnail_path: str = ""
    is_hardware: bool = True
    pan_position: Optional[int] = None
    tilt_position: Optional[int] = None
    zoom_position: Optional[int] = None
    image_settings: Optional[ImageSettings] = None

    def __post_init__(self):
        if not self.name:
            self.name = f"Preset {self.number}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "thumbnail_path": self.thumbnail_path,
            "is_hardware": self.is_hardware,
            "pan_position": self.pan_position,
            "tilt_position": self.tilt_position,
            "zoom_position": self.zoom_position,
            "image_settings": self.image_settings.to_dict() if self.image_settings else None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Preset':
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "image_settings"}
        if "image_settings" in data and data["image_settings"]:
            kwargs["image_settings"] = ImageSettings.from_dict(data["image_settings"])
        return cls(**kwargs)

@dataclass
class Profile:
    name: str
    camera_config: CameraConfig = field(default_factory=CameraConfig)
    image_settings: ImageSettings = field(default_factory=ImageSettings)
    presets: list[Preset] = field(default_factory=list)
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "camera_config": self.camera_config.to_dict(),
            "image_settings": self.image_settings.to_dict(),
            "presets": [p.to_dict() for p in self.presets],
            "is_active": self.is_active
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Profile':
        kwargs = {}
        if "name" in data:
            kwargs["name"] = data["name"]
        if "camera_config" in data:
            kwargs["camera_config"] = CameraConfig.from_dict(data["camera_config"])
        if "image_settings" in data:
            kwargs["image_settings"] = ImageSettings.from_dict(data["image_settings"])
        if "presets" in data:
            kwargs["presets"] = [Preset.from_dict(p) for p in data["presets"]]
        if "is_active" in data:
            kwargs["is_active"] = data["is_active"]
        return cls(**kwargs)

    def save(self, directory: Path) -> None:
        """Save profile to JSON file"""
        directory.mkdir(parents=True, exist_ok=True)
        if not self.name.strip() or self.name in (".", "..") or any(c in self.name for c in "/\\"):
            raise ValueError("Nome de perfil inválido")
        filepath = directory / f"{self.name}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: Path) -> 'Profile':
        """Load profile from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
