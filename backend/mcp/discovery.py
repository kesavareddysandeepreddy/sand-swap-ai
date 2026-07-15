"""MCP discovery façade."""

from __future__ import annotations

from backend.mcp.capabilities import CapabilityDiscovery
from backend.mcp.models import MCPDiscoverySnapshot, MCPServerMetadata


class MCPDiscoveryService:
    """High-level discovery API for MCP server metadata and capabilities."""

    def __init__(self, capability_discovery: CapabilityDiscovery) -> None:
        self.capability_discovery = capability_discovery

    def discover_from_metadata(
        self, metadata: MCPServerMetadata
    ) -> MCPDiscoverySnapshot:
        """Persist capability snapshot using metadata defaults only."""
        return self.capability_discovery.discover(metadata=metadata)

    def get_snapshot(self, server_name: str) -> MCPDiscoverySnapshot | None:
        """Fetch an existing snapshot for a server."""
        return self.capability_discovery.get(server_name)

    def list_snapshots(self) -> list[MCPDiscoverySnapshot]:
        """List all discovered snapshots."""
        return self.capability_discovery.list_all()
