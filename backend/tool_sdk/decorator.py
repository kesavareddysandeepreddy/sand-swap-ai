"""Decorator helpers for Tool SDK plugin metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.tool_sdk.registry import _auto_register_tool_class


def tool(
    *,
    name: str,
    description: str,
    capabilities: list[str],
    priority: int = 100,
) -> Callable[[type], type]:
    """Attach declarative metadata to a tool class."""

    def _decorator(cls: type) -> type:
        metadata: dict[str, Any] = {
            "name": name,
            "description": description,
            "capabilities": list(capabilities),
            "priority": priority,
        }
        setattr(cls, "__tool_metadata__", metadata)
        _auto_register_tool_class(cls)
        return cls

    return _decorator
