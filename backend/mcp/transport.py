"""MCP transport abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.mcp.context import MCPRequestContext
from backend.mcp.models import (
    MCPDiscoverySnapshot,
    MCPResourceContent,
    MCPToolCallResult,
)


class MCPTransport(ABC):
    """Abstract transport contract for MCP protocols."""

    @abstractmethod
    def connect(
        self, endpoint: str, *, context: MCPRequestContext | None = None
    ) -> None:
        """Establish transport connection."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, endpoint: str) -> None:
        """Close transport connection."""
        raise NotImplementedError

    @abstractmethod
    def discover(self, endpoint: str) -> MCPDiscoverySnapshot:
        """Discover capabilities from a server endpoint."""
        raise NotImplementedError

    @abstractmethod
    def call_tool(
        self,
        endpoint: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolCallResult:
        """Invoke a tool over transport."""
        raise NotImplementedError

    @abstractmethod
    def read_resource(self, endpoint: str, uri: str) -> MCPResourceContent:
        """Read a resource over transport."""
        raise NotImplementedError


class NoopTransport(MCPTransport):
    """Safe default transport for metadata-only framework mode."""

    def __init__(self, transport_name: str) -> None:
        self.transport_name = transport_name
        self._connected_endpoints: set[str] = set()

    def connect(
        self, endpoint: str, *, context: MCPRequestContext | None = None
    ) -> None:
        _ = context
        self._connected_endpoints.add(endpoint)

    def disconnect(self, endpoint: str) -> None:
        self._connected_endpoints.discard(endpoint)

    def discover(self, endpoint: str) -> MCPDiscoverySnapshot:
        return MCPDiscoverySnapshot(
            server_name=endpoint,
            version="0.1.0",
            tools=[],
            resources=[],
            prompts=[],
            capabilities=[],
        )

    def call_tool(
        self,
        endpoint: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolCallResult:
        _ = arguments
        return MCPToolCallResult(
            server_name=endpoint,
            tool_name=tool_name,
            content={"status": "noop"},
            latency_ms=0.0,
        )

    def read_resource(self, endpoint: str, uri: str) -> MCPResourceContent:
        return MCPResourceContent(
            server_name=endpoint,
            uri=uri,
            content="",
            mime_type="text/plain",
        )
