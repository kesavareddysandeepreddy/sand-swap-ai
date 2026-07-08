"""
Dependency Injection Container
"""

from typing import Any


class Container:
    """Singleton Dependency Injection Container."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._dependencies = {}
        return cls._instance

    def register(self, name: str, dependency: Any) -> None:
        self._dependencies[name] = dependency

    def resolve(self, name: str) -> Any:
        if name not in self._dependencies:
            raise KeyError(f"Dependency '{name}' not registered.")
        return self._dependencies[name]

    def exists(self, name: str) -> bool:
        return name in self._dependencies

    def remove(self, name: str) -> None:
        self._dependencies.pop(name, None)

    def clear(self) -> None:
        self._dependencies.clear()

    def list(self) -> list[str]:
        return sorted(self._dependencies.keys())
