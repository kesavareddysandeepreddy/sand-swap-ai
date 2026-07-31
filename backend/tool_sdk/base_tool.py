"""Base interface for Tool SDK plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.tool_sdk.context import ToolContext


class BaseTool(ABC):
    """Abstract base for self-contained tool plugins."""

    @abstractmethod
    def name(self) -> str:
        """Return stable tool identifier."""
        raise NotImplementedError

    @abstractmethod
    def description(self) -> str:
        """Return human-readable tool description."""
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> list[str]:
        """Return declared tool capabilities."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: ToolContext | dict[str, Any]) -> Any:
        """Execute tool call for given context."""
        raise NotImplementedError

    def validate(self, context: ToolContext | dict[str, Any] | None = None) -> bool:
        """Optional validation hook for tool readiness."""
        _ = context
        return True

    def health(self) -> dict[str, object]:
        """Optional health diagnostics."""
        return {"status": "ok", "tool": self.name()}
