"""MCP client supporting multiple simultaneous servers."""

from __future__ import annotations

import time
from typing import Any

from backend.core.logging.logger import LoggerFactory
from backend.mcp.capabilities import CapabilityDiscovery
from backend.mcp.context import MCPRequestContext
from backend.mcp.models import (
    MCPDiscoverySnapshot,
    MCPResource,
    MCPResourceContent,
    MCPServerMetadata,
    MCPTool,
    MCPToolCallResult,
)
from backend.mcp.registry import MCPRegistry
from backend.mcp.session import MCPSessionManager
from backend.mcp.transport import MCPTransport, NoopTransport


class MCPClient:
    """Client facade for MCP operations across multiple servers."""

    def __init__(
        self,
        *,
        registry: MCPRegistry,
        capability_discovery: CapabilityDiscovery,
        session_manager: MCPSessionManager,
        transports: dict[str, MCPTransport] | None = None,
    ) -> None:
        self.registry = registry
        self.capability_discovery = capability_discovery
        self.session_manager = session_manager
        self._transports = transports or {
            "stdio": NoopTransport("stdio"),
            "http": NoopTransport("http"),
            "sse": NoopTransport("sse"),
            "websocket": NoopTransport("websocket"),
        }
        self.logger = LoggerFactory.get_logger("MCPClient")

    def _resolve_server(self, server_name: str) -> MCPServerMetadata:
        server = self.registry.get_server(server_name)
        if server is None:
            raise KeyError(f"Unknown MCP server: {server_name}")
        return server

    def _resolve_transport(self, server: MCPServerMetadata) -> MCPTransport:
        transport = self._transports.get(server.transport)
        if transport is None:
            raise KeyError(f"Unsupported MCP transport: {server.transport}")
        return transport

    def connect(
        self,
        server_name: str,
        *,
        request_context: MCPRequestContext | None = None,
    ) -> MCPDiscoverySnapshot:
        server = self._resolve_server(server_name)
        transport = self._resolve_transport(server)
        endpoint = server.endpoint or server.name

        self.session_manager.set_state(server_name, "connecting")
        self.logger.info(
            "MCP connect server=%s transport=%s", server_name, server.transport
        )

        start = time.perf_counter()
        try:
            transport.connect(endpoint, context=request_context)
            discovered = transport.discover(endpoint)
            snapshot = self.capability_discovery.discover(
                metadata=server,
                tools=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                    }
                    for tool in discovered.tools
                ],
                resources=[
                    {
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": resource.description,
                        "mime_type": resource.mime_type,
                    }
                    for resource in discovered.resources
                ],
                prompts=[
                    {
                        "name": prompt.name,
                        "description": prompt.description,
                    }
                    for prompt in discovered.prompts
                ],
                capabilities=discovered.capabilities,
            )
            self.session_manager.set_state(server_name, "connected")
            self.session_manager.apply_discovery(server_name, snapshot)
            self.session_manager.heartbeat(server_name)
            latency_ms = (time.perf_counter() - start) * 1000
            self.logger.info(
                "MCP connected server=%s latency_ms=%.3f", server_name, latency_ms
            )
            return snapshot
        except Exception as exc:  # noqa: BLE001
            self.session_manager.set_state(server_name, "error", error=str(exc))
            self.logger.exception(
                "MCP connect error server=%s error=%s", server_name, exc
            )
            raise

    def disconnect(self, server_name: str) -> None:
        server = self._resolve_server(server_name)
        transport = self._resolve_transport(server)
        endpoint = server.endpoint or server.name
        transport.disconnect(endpoint)
        self.session_manager.set_state(server_name, "disconnected")
        self.logger.info("MCP disconnect server=%s", server_name)

    def list_tools(self, server_name: str) -> list[MCPTool]:
        snapshot = self.capability_discovery.get(server_name)
        if snapshot is None:
            return []
        return list(snapshot.tools)

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolCallResult:
        server = self._resolve_server(server_name)
        transport = self._resolve_transport(server)
        endpoint = server.endpoint or server.name

        start = time.perf_counter()
        try:
            result = transport.call_tool(endpoint, tool_name, arguments)
            result.server_name = server_name
            result.tool_name = tool_name
            result.latency_ms = (time.perf_counter() - start) * 1000
            self.session_manager.heartbeat(server_name)
            self.logger.info(
                "MCP tool call server=%s tool=%s latency_ms=%.3f",
                server_name,
                tool_name,
                result.latency_ms,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start) * 1000
            self.session_manager.set_state(server_name, "error", error=str(exc))
            self.logger.exception(
                "MCP tool call error server=%s tool=%s latency_ms=%.3f error=%s",
                server_name,
                tool_name,
                latency_ms,
                exc,
            )
            return MCPToolCallResult(
                server_name=server_name,
                tool_name=tool_name,
                is_error=True,
                error=str(exc),
                latency_ms=latency_ms,
            )

    def list_resources(self, server_name: str) -> list[MCPResource]:
        snapshot = self.capability_discovery.get(server_name)
        if snapshot is None:
            return []
        return list(snapshot.resources)

    def read_resource(self, server_name: str, uri: str) -> MCPResourceContent:
        server = self._resolve_server(server_name)
        transport = self._resolve_transport(server)
        endpoint = server.endpoint or server.name
        result = transport.read_resource(endpoint, uri)
        result.server_name = server_name
        self.session_manager.heartbeat(server_name)
        return result

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "servers": [server.name for server in self.registry.list_servers()],
            "sessions": self.session_manager.health(),
            "discovery": self.capability_discovery.health(),
        }
