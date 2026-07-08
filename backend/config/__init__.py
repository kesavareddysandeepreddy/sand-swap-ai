from .config_manager import ConfigManager
from .settings import settings

config = ConfigManager()

__all__ = [
    "settings",
    "config",
    "ConfigManager",
]
