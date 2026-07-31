"""Project memory models for conversation summaries and decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True)
class ConversationSummary:
    """Represents one persisted summary snapshot for a conversation."""

    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    conversation_id: str = ""
    sequence: int = 1
    title: str = ""
    summary: str = ""
    key_topics: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class DecisionRecord:
    """Represents a project-scoped decision captured from conversations."""

    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    title: str = ""
    decision: str = ""
    reason: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ProjectMemorySummary:
    """High-level snapshot of project memory footprint."""

    total_conversations: int = 0
    total_decisions: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
