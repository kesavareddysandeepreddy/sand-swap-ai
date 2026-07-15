"""Capability discovery and snapshot storage."""

from __future__ import annotations

from backend.mcp.models import MCPDiscoverySnapshot, MCPServerMetadata


class CapabilityDiscovery:
    """Manage discovered MCP capability snapshots."""

    def __init__(self) -> None:
        self._snapshots: dict[str, MCPDiscoverySnapshot] = {}

    def discover(
        self,
        *,
        metadata: MCPServerMetadata,
        tools: list[dict[str, object]] | None = None,
        resources: list[dict[str, object]] | None = None,
        prompts: list[dict[str, object]] | None = None,
        capabilities: list[str] | None = None,
    ) -> MCPDiscoverySnapshot:
        snapshot = MCPDiscoverySnapshot(
            server_name=metadata.name,
            version=metadata.version,
            tools=[],
            resources=[],
            prompts=[],
            capabilities=capabilities or list(metadata.capabilities),
        )
        if tools:
            from backend.mcp.models import MCPTool

            snapshot.tools = [
                MCPTool(
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                    input_schema=dict(item.get("input_schema", {})),
                )
                for item in tools
            ]
        if resources:
            from backend.mcp.models import MCPResource

            snapshot.resources = [
                MCPResource(
                    uri=str(item.get("uri", "")),
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                    mime_type=str(item.get("mime_type", "text/plain")),
                )
                for item in resources
            ]
        if prompts:
            from backend.mcp.models import MCPPrompt

            snapshot.prompts = [
                MCPPrompt(
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                )
                for item in prompts
            ]

        self._snapshots[metadata.name] = snapshot
        return snapshot

    def get(self, server_name: str) -> MCPDiscoverySnapshot | None:
        """Return snapshot for a server."""
        return self._snapshots.get(server_name)

    def list_all(self) -> list[MCPDiscoverySnapshot]:
        """List all snapshots."""
        return [self._snapshots[name] for name in sorted(self._snapshots.keys())]

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "discovered_servers": sorted(self._snapshots.keys()),
        }
