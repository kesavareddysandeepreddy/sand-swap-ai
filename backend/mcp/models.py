"""Core MCP framework models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TransportType = Literal["stdio", "http", "sse", "websocket"]
SessionState = Literal["disconnected", "connecting", "connected", "error"]


@dataclass(slots=True)
class MCPTool:
    """Metadata describing a tool exposed by an MCP server."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPResource:
    """Metadata describing a resource exposed by an MCP server."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


@dataclass(slots=True)
class MCPPrompt:
    """Metadata describing an MCP prompt template."""

    name: str
    description: str = ""


@dataclass(slots=True)
class MCPServerMetadata:
    """Static metadata for a configured MCP server."""

    name: str
    version: str = "0.1.0"
    transport: TransportType = "stdio"
    endpoint: str = ""
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPDiscoverySnapshot:
    """Discovered MCP server capabilities and surfaces."""

    server_name: str
    version: str
    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)
    prompts: list[MCPPrompt] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MCPToolCallResult:
    """Result returned from an MCP tool invocation."""

    server_name: str
    tool_name: str
    content: Any = None
    latency_ms: float = 0.0
    is_error: bool = False
    error: str | None = None


@dataclass(slots=True)
class MCPResourceContent:
    """Resource content payload returned from MCP server."""

    server_name: str
    uri: str
    content: Any
    mime_type: str = "text/plain"
