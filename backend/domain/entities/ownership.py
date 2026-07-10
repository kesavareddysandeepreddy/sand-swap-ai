"""Ownership link entities for enterprise resource boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ConversationOwner:
    """Maps an existing conversation to a user owner."""

    conversation_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class DocumentOwner:
    """Maps an existing document to a user and project owner context."""

    document_id: str
    user_id: str
    project_id: str


@dataclass(frozen=True, slots=True)
class MemoryOwner:
    """Maps an existing memory item to a user and project owner context."""

    memory_id: str
    user_id: str
    project_id: str


@dataclass(frozen=True, slots=True)
class AgentOwner:
    """Future-ready mapping for ownership of agent resources."""

    agent_id: str
    user_id: str
    project_id: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        user_id: str,
        project_id: str,
    ) -> "AgentOwner":
        """Construct a new agent ownership binding."""
        return cls(
            agent_id=agent_id,
            user_id=user_id,
            project_id=project_id,
            created_at=datetime.now(UTC),
        )
