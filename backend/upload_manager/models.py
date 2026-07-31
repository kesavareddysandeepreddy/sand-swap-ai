"""Domain models for upload sessions and jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class UploadStage(StrEnum):
    """Deterministic upload pipeline stages."""

    VALIDATION = "Validation"
    PARSER_SELECTION = "Parser Selection"
    OCR_REQUIRED = "OCR Required"
    CHUNK_REQUIRED = "Chunk Required"
    EMBEDDING_REQUIRED = "Embedding Required"
    KNOWLEDGE_GRAPH_REQUIRED = "Knowledge Graph Required"
    FINISHED = "Finished"


@dataclass(slots=True)
class UploadSession:
    """Represents one project-scoped upload session."""

    project_id: str
    source_id: str
    status: str = "pending"
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    current_file: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


@dataclass(slots=True)
class UploadJob:
    """Represents one file-level upload job within a session."""

    session_id: str
    file_name: str
    file_size: int
    mime_type: str
    parser: str
    status: str = "queued"
    chunks_created: int = 0
    embeddings_created: int = 0
    error: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime | None = None
    completed_at: datetime | None = None
