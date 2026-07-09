"""RAG domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class DocumentRecord:
    """Metadata persisted for an uploaded document."""

    id: str
    name: str
    original_filename: str
    stored_path: str
    file_type: str
    size_bytes: int
    sha256: str
    chunk_count: int = 0
    embedding_status: str = "pending"
    index_status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ParsedDocument:
    """Structured output from parser layer."""

    text: str
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentChunk:
    """Chunk ready for embedding and indexing."""

    id: str
    document_id: str
    document_name: str
    text: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IndexedChunk:
    """Vector-indexed chunk payload."""

    chunk: DocumentChunk
    vector: list[float]


@dataclass(slots=True)
class RetrievedChunk:
    """Retrieved chunk with score and source information."""

    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
