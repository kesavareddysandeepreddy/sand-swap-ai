"""
Central Service Registry
"""

from typing import Any


class ServiceRegistry:
    """Singleton registry for application services."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services = {}
        return cls._instance

    def register(self, name: str, service: Any) -> None:
        self._services[name] = service

    def get(self, name: str) -> Any:
        if name not in self._services:
            raise KeyError(f"Service '{name}' is not registered.")
        return self._services[name]

    def exists(self, name: str) -> bool:
        return name in self._services

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)

    def clear(self) -> None:
        self._services.clear()

    def list_services(self) -> list[str]:
        return sorted(self._services.keys())
