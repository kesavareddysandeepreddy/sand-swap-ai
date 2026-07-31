"""Domain models for project knowledge sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from backend.knowledge_sources.source_types import SourceType


@dataclass(slots=True)
class KnowledgeSource:
    """Represents one connector attached to a project."""

    project_id: str
    name: str
    source_type: SourceType
    connection_config: dict[str, object] = field(default_factory=dict)
    enabled: bool = True
    status: str = "pending"
    file_count: int = 0
    chunk_count: int = 0
    embedding_count: int = 0
    last_sync: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
