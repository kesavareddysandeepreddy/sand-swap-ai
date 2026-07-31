"""Tool metadata model used for capability-based selection."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolMetadata:
    """Describes tool capabilities and selection attributes."""

    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    supported_inputs: list[str] = field(default_factory=list)
    supported_outputs: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    priority: int = 0
