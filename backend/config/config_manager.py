"""
Central Configuration Manager
"""

from pathlib import Path

import yaml


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            config_path = Path(__file__).parent / "config.yaml"

            with open(config_path, "r", encoding="utf-8") as file:
                cls._instance._config = yaml.safe_load(file)

        return cls._instance

    def get(self, key: str, default=None):
        value = self._config

        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default

        return value if value is not None else default
