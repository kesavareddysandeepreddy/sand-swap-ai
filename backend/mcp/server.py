"""MCP server handle abstractions."""

from __future__ import annotations

from dataclasses import dataclass

from backend.mcp.models import MCPServerMetadata


@dataclass(slots=True)
class MCPServerHandle:
    """Simple server handle bound to metadata."""

    metadata: MCPServerMetadata

    @property
    def name(self) -> str:
        return self.metadata.name
