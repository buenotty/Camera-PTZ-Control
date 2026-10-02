import json
import os
from pathlib import Path
from typing import Any, Dict
from PySide6.QtCore import QObject, Signal

def deep_merge(dict1: dict, dict2: dict) -> dict:
    """Recursively merges dict2 into dict1."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

class SettingsManager(QObject):
    """
    Singleton SettingsManager.
    Loads and saves settings to %APPDATA%/PTZ Control/settings.json.
    Merges with defaults from config/default_settings.json.
    """
    _instance = None
    settings_changed = Signal(str, object)  # Emits (key, new_value) when a setting changes

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SettingsManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        super().__init__()
        self._initialized = True

        # Determine paths
        app_data = os.environ.get('APPDATA', os.path.expanduser('~/.config'))
        self.settings_dir = Path(app_data) / "PTZ Control"
        self.settings_file = self.settings_dir / "settings.json"

        project_root = Path(__file__).parent.parent.parent
        self.default_settings_file = project_root / "config" / "default_settings.json"

        self.settings: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Loads settings from default config and user settings."""
        defaults = {}
        if self.default_settings_file.exists():
            try:
                with open(self.default_settings_file, 'r', encoding='utf-8') as f:
                    defaults = json.load(f)
            except Exception as e:
                print(f"Error loading defaults: {e}")

        user_settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    user_settings = json.load(f)
            except Exception as e:
                print(f"Error loading user settings: {e}")

        self.settings = deep_merge(defaults, user_settings)

    def save(self) -> None:
        """Saves current settings to the user's APPDATA directory."""
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a setting value using dot notation.
        Example: get('camera.ip')
        """
        keys = key.split('.')
        value = self.settings
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Sets a setting value using dot notation and auto-saves.
        Emits settings_changed signal.
        Example: set('camera.ip', '192.168.1.100')
        """
        keys = key.split('.')
        current = self.settings
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
        self.save()
        self.settings_changed.emit(key, value)
