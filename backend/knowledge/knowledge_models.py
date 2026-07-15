"""Knowledge engine models for semantic file intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class KnowledgeObject:
    """Persistent semantic representation of an uploaded file."""

    id: str = field(default_factory=lambda: str(uuid4()))
    workspace_id: str = "default"
    project_id: str = "default"
    conversation_id: str | None = None
    document_id: str | None = None
    filename: str = ""
    mime_type: str = "application/octet-stream"
    file_type: str = "unknown"
    storage_path: str = ""
    thumbnail_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "created"
    semantic_summary: str = ""
    description: str = ""
    objects: list[str] = field(default_factory=list)
    ocr_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    embeddings: list[float] = field(default_factory=list)
    vision_analysis: dict[str, Any] = field(default_factory=dict)
    attachment_metadata: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    processing_history: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    processing_time: float = 0.0
    version: int = 1


@dataclass(slots=True)
class KnowledgeContext:
    """User-facing context composed from one or more knowledge objects."""

    knowledge_ids: list[str] = field(default_factory=list)
    rendered_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
