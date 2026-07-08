"""
SandSwap AI - Memory Record
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class MemoryRecord:
    """Represents a single persistent memory."""

    id: str = field(default_factory=lambda: str(uuid4()))

    user_id: str = ""
    project_id: str | None = None
    conversation_id: str | None = None

    memory_type: str = ""
    category: str = ""

    key: str = ""
    value: str = ""
    summary: str = ""

    importance: float = 0.5
    confidence: float = 1.0

    source: str = "chat"

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime | None = None

    access_count: int = 0

    expires_at: datetime | None = None

    embedding_id: str | None = None
    parent_memory_id: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and datetime.now(UTC) > self.expires_at

    def touch(self) -> None:
        self.access_count += 1
        self.last_accessed = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def update(
        self,
        value: str,
        *,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> None:
        self.value = value

        if importance is not None:
            self.importance = importance

        if confidence is not None:
            self.confidence = confidence

        self.updated_at = datetime.now(UTC)
