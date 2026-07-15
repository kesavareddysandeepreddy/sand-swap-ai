from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.agents.context import AgentExecutionContext
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.mcp.capabilities import CapabilityDiscovery
from backend.mcp.client import MCPClient
from backend.mcp.discovery import MCPDiscoveryService
from backend.mcp.models import (
    MCPDiscoverySnapshot,
    MCPResourceContent,
    MCPTool,
    MCPToolCallResult,
)
from backend.mcp.registry import MCPRegistry
from backend.mcp.session import MCPSessionManager
from backend.mcp.transport import MCPTransport
from backend.workflows.models import WorkflowTask


@dataclass(slots=True)
class _FakeTransport(MCPTransport):
    connected: bool = False

    def connect(self, endpoint: str, *, context=None) -> None:  # type: ignore[override]
        _ = (endpoint, context)
        self.connected = True

    def disconnect(self, endpoint: str) -> None:
        _ = endpoint
        self.connected = False

    def discover(self, endpoint: str) -> MCPDiscoverySnapshot:
        _ = endpoint
        return MCPDiscoverySnapshot(
            server_name="filesystem",
            version="1.0.0",
            tools=[MCPTool(name="read_file", description="Read files")],
            resources=[],
            prompts=[],
            capabilities=["tools", "resources"],
        )

    def call_tool(
        self,
        endpoint: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolCallResult:
        _ = (endpoint, arguments)
        return MCPToolCallResult(
            server_name="filesystem",
            tool_name=tool_name,
            content={"ok": True},
        )

    def read_resource(self, endpoint: str, uri: str) -> MCPResourceContent:
        _ = endpoint
        return MCPResourceContent(
            server_name="filesystem",
            uri=uri,
            content="hello",
            mime_type="text/plain",
        )


def _build_client() -> MCPClient:
    registry = MCPRegistry()
    registry.register_default_servers()
    discovery = CapabilityDiscovery()
    session_manager = MCPSessionManager()
    transport = _FakeTransport()
    return MCPClient(
        registry=registry,
        capability_discovery=discovery,
        session_manager=session_manager,
        transports={
            "stdio": transport,
            "http": transport,
            "sse": transport,
            "websocket": transport,
        },
    )


def _agent_context() -> AgentExecutionContext:
    conversation = Conversation(user_id="u1", id="u1:mcp")
    return AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt="Run MCP task",
        prompt="prompt",
        system_prompt="system",
    )


def test_registry_defaults_present() -> None:
    registry = MCPRegistry()
    registry.register_default_servers()

    names = [server.name for server in registry.list_servers()]

    assert names == [
        "browser",
        "database",
        "email",
        "filesystem",
        "github",
        "jira",
        "local_python",
        "slack",
    ]


def test_client_connect_list_and_disconnect() -> None:
    client = _build_client()

    snapshot = client.connect("filesystem")
    tools = client.list_tools("filesystem")
    resources = client.list_resources("filesystem")
    client.disconnect("filesystem")

    assert snapshot.server_name == "filesystem"
    assert tools and tools[0].name == "read_file"
    assert resources == []


def test_client_tool_and_resource_calls() -> None:
    client = _build_client()
    client.connect("filesystem")

    tool_result = client.call_tool("filesystem", "read_file", {"path": "a.txt"})
    resource = client.read_resource("filesystem", "file://a.txt")

    assert tool_result.is_error is False
    assert tool_result.content == {"ok": True}
    assert resource.content == "hello"


def test_discovery_service_uses_metadata_defaults() -> None:
    registry = MCPRegistry()
    registry.register_default_servers()
    discovery = CapabilityDiscovery()
    service = MCPDiscoveryService(discovery)

    for server in registry.list_servers():
        service.discover_from_metadata(server)

    snapshots = service.list_snapshots()

    assert len(snapshots) == 8
    assert any(item.server_name == "github" for item in snapshots)


def test_session_manager_tracks_state_and_heartbeat() -> None:
    manager = MCPSessionManager()

    manager.set_state("filesystem", "connecting")
    manager.set_state("filesystem", "connected")
    manager.heartbeat("filesystem")

    session = manager.get("filesystem")
    assert session is not None
    assert session.state == "connected"
    assert session.last_heartbeat_at is not None


def test_tool_router_invokes_mcp_transparently() -> None:
    client = _build_client()
    client.connect("filesystem")

    router = ToolRouter()
    router.register_tool("MCP", client)

    result = router.invoke_task(
        task=WorkflowTask(
            task_id="t1",
            name="MCP:filesystem.read_file",
            action="call_tool",
            tool_name="MCP",
            mcp_server="filesystem",
            mcp_tool="read_file",
            mcp_arguments={"path": "a.txt"},
        ),
        context=_agent_context(),
    )

    assert result["status"] == "completed"
    assert result["tool"] == "MCP"
    assert result["result"]["server"] == "filesystem"
