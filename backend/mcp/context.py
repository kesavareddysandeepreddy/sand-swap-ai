"""MCP request and operation context models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPRequestContext:
    """Context metadata passed across MCP operations."""

    user_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    conversation_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
