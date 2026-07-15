"""MCP server metadata registry."""

from __future__ import annotations

from backend.mcp.models import MCPServerMetadata


class MCPRegistry:
    """Register and resolve MCP server metadata."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerMetadata] = {}

    def register_server(self, server: MCPServerMetadata) -> None:
        """Register MCP server metadata."""
        self._servers[server.name] = server

    def get_server(self, server_name: str) -> MCPServerMetadata | None:
        """Resolve server metadata by name."""
        return self._servers.get(server_name)

    def list_servers(self) -> list[MCPServerMetadata]:
        """List all registered servers."""
        return [self._servers[name] for name in sorted(self._servers.keys())]

    def register_default_servers(self) -> None:
        """Register default MCP server metadata entries."""
        defaults = [
            MCPServerMetadata(
                name="filesystem",
                transport="stdio",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="github",
                transport="http",
                endpoint="https://api.github.com/mcp",
                capabilities=["tools", "resources", "prompts"],
            ),
            MCPServerMetadata(
                name="jira",
                transport="http",
                endpoint="https://jira.local/mcp",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="slack",
                transport="sse",
                endpoint="https://slack.local/mcp",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="email",
                transport="http",
                endpoint="https://email.local/mcp",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="browser",
                transport="stdio",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="database",
                transport="stdio",
                capabilities=["tools", "resources"],
            ),
            MCPServerMetadata(
                name="local_python",
                transport="stdio",
                capabilities=["tools", "resources"],
            ),
        ]
        for server in defaults:
            self.register_server(server)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "servers": [server.name for server in self.list_servers()],
        }
