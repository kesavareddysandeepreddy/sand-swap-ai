"""Tool resolution helpers for execution planning."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from backend.tool_sdk.registry import ToolRegistry
from backend.tools.capability_registry import CapabilityRegistry


@dataclass(slots=True)
class ToolResolution:
    """Resolved tool instance and metadata for one capability."""

    capability: str
    tool_name: str
    tool: Any
    priority: int
    source: str


class ToolResolver:
    """Resolve tools by capability using deterministic priority ordering."""

    def __init__(
        self,
        *,
        capability_registry: CapabilityRegistry,
        tool_registry: ToolRegistry,
        tool_router: Any | None = None,
    ) -> None:
        self.capability_registry = capability_registry
        self.tool_registry = tool_registry
        self.tool_router = tool_router

    @staticmethod
    def _instantiate_tool(tool_class: type) -> Any:
        signature = inspect.signature(tool_class)
        if "execution_recorder" in signature.parameters:
            return tool_class()
        return tool_class()

    def _resolve_from_registry(self, tool_name: str) -> Any | None:
        tool_class = self.tool_registry.get(tool_name)
        if tool_class is None:
            return None
        return self._instantiate_tool(tool_class)

    def resolve(self, capability: str) -> ToolResolution | None:
        normalized = capability.strip().lower()
        if not normalized:
            return None

        candidates = self.capability_registry.find_by_capability(normalized)
        for metadata in candidates:
            tool = self._resolve_from_registry(metadata.name)
            if tool is not None:
                return ToolResolution(
                    capability=normalized,
                    tool_name=metadata.name,
                    tool=tool,
                    priority=metadata.priority,
                    source="tool_registry",
                )

            if self.tool_router is not None:
                routed_tool = self.tool_router.lookup(metadata.name)
                if routed_tool is not None:
                    return ToolResolution(
                        capability=normalized,
                        tool_name=metadata.name,
                        tool=routed_tool,
                        priority=metadata.priority,
                        source="tool_router",
                    )

        return None
