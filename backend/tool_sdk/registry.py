"""Tool SDK registry with optional bridge to capability metadata registry."""

from __future__ import annotations

from backend.tools.capability_registry import CapabilityRegistry
from backend.tools.tool_metadata import ToolMetadata


class ToolRegistry:
    """Register and discover SDK tools independently of runtime router."""

    def __init__(self, capability_registry: CapabilityRegistry | None = None) -> None:
        self._tools: dict[str, type] = {}
        self.capability_registry = capability_registry

    @staticmethod
    def _metadata_from_tool_class(tool_class: type) -> ToolMetadata:
        metadata = getattr(tool_class, "__tool_metadata__", None)
        if not isinstance(metadata, dict):
            raise ValueError("Tool class is missing @tool metadata.")

        return ToolMetadata(
            name=str(metadata.get("name", "")).strip(),
            description=str(metadata.get("description", "")).strip(),
            capabilities=list(metadata.get("capabilities", [])),
            supported_inputs=[],
            supported_outputs=[],
            permissions=[],
            priority=int(metadata.get("priority", 100)),
        )

    def register(self, tool_class: type) -> None:
        """Register a tool class and bridge metadata when configured."""
        metadata = self._metadata_from_tool_class(tool_class)
        if not metadata.name:
            raise ValueError("Tool name cannot be empty.")
        self._tools[metadata.name] = tool_class
        if self.capability_registry is not None:
            self.capability_registry.register_tool(metadata)

    def unregister(self, name: str) -> None:
        """Unregister a tool class by name."""
        self._tools.pop(name, None)
        if self.capability_registry is not None:
            self.capability_registry.unregister_tool(name)

    def get(self, name: str) -> type | None:
        """Resolve one tool class by name."""
        return self._tools.get(name)

    def list(self) -> list[type]:
        """Return registered tool classes in deterministic name order."""
        return [self._tools[name] for name in sorted(self._tools.keys())]

    def find_by_capability(self, capability: str) -> list[type]:
        """Find tool classes matching capability ordered by priority then name."""
        normalized = capability.strip().lower()
        if not normalized:
            return []

        matches: list[tuple[int, str, type]] = []
        for tool_class in self._tools.values():
            metadata = self._metadata_from_tool_class(tool_class)
            capabilities = [item.lower() for item in metadata.capabilities]
            if normalized in capabilities:
                matches.append((metadata.priority, metadata.name, tool_class))

        matches.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in matches]


default_tool_registry = ToolRegistry()


def _auto_register_tool_class(tool_class: type) -> None:
    """Internal helper used by decorators for auto-registration."""
    default_tool_registry.register(tool_class)
