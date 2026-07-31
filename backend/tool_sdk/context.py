"""Shared tool execution context model."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(slots=True)
class ToolContext:
    """Common context shape for Tool SDK plugins.

    Attachments are normalized to an immutable tuple while variables and metadata
    stay mutable for request-scoped updates during execution.
    """

    project_id: str = ""
    conversation_id: str = ""
    user_id: str = ""
    workspace_id: str = ""
    attachments: tuple[str, ...] = field(default_factory=tuple)
    variables: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_trace_id: str | None = None

    def __post_init__(self) -> None:
        self.attachments = tuple(self.attachments)

    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like accessor used by existing tool implementations."""
        lookup = MappingProxyType(
            {
                "project_id": self.project_id,
                "conversation_id": self.conversation_id,
                "user_id": self.user_id,
                "workspace_id": self.workspace_id,
                "attachments": self.attachments,
                "variables": self.variables,
                "metadata": self.metadata,
                "execution_trace_id": self.execution_trace_id,
                **self.variables,
                **self.metadata,
            }
        )
        return lookup.get(key, default)
