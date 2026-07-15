"""MCP session management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.mcp.models import MCPDiscoverySnapshot, SessionState


@dataclass(slots=True)
class MCPSession:
    """State holder for an MCP connection session."""

    server_name: str
    state: SessionState = "disconnected"
    capabilities: list[str] = field(default_factory=list)
    connected_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None


class MCPSessionManager:
    """Manage active MCP sessions and heartbeat state."""

    def __init__(self) -> None:
        self._sessions: dict[str, MCPSession] = {}

    def get_or_create(self, server_name: str) -> MCPSession:
        session = self._sessions.get(server_name)
        if session is None:
            session = MCPSession(server_name=server_name)
            self._sessions[server_name] = session
        return session

    def set_state(
        self, server_name: str, state: SessionState, *, error: str | None = None
    ) -> MCPSession:
        session = self.get_or_create(server_name)
        session.state = state
        session.last_error = error
        if state == "connected" and session.connected_at is None:
            session.connected_at = datetime.now(UTC)
        return session

    def apply_discovery(
        self, server_name: str, snapshot: MCPDiscoverySnapshot
    ) -> MCPSession:
        session = self.get_or_create(server_name)
        session.capabilities = list(snapshot.capabilities)
        return session

    def heartbeat(self, server_name: str) -> MCPSession:
        session = self.get_or_create(server_name)
        session.last_heartbeat_at = datetime.now(UTC)
        return session

    def get(self, server_name: str) -> MCPSession | None:
        return self._sessions.get(server_name)

    def list_sessions(self) -> list[MCPSession]:
        return [self._sessions[name] for name in sorted(self._sessions.keys())]

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "active_sessions": [
                {
                    "server": session.server_name,
                    "state": session.state,
                }
                for session in self.list_sessions()
            ],
        }
