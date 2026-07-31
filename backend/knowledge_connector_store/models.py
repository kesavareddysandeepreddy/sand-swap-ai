"""Persistent models for connector store records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.knowledge_sources.source_types import SourceType


@dataclass(slots=True)
class ConnectorCredentials:
    """Connector credentials payload designed for secure storage providers."""

    reference: str = ""
    encrypted_payload: str = ""
    provider: str = "inline"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorConfiguration:
    """Connector configuration payload persisted for runtime restoration."""

    settings: dict[str, Any] = field(default_factory=dict)
    workspace_id: str = "default"
    project_id: str = "default"


@dataclass(slots=True)
class ConnectorSyncState:
    """Persisted synchronization cursor and timestamps for one connector."""

    status: str = "pending"
    last_sync_at: datetime | None = None
    last_incremental_sync_at: datetime | None = None
    cursor: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorStatistics:
    """Persisted indexing statistics for one connector."""

    files_indexed: int = 0
    chunks_indexed: int = 0
    embeddings_indexed: int = 0
    errors_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorRecord:
    """Persistence model for one project-scoped connector registration."""

    source_id: str
    source_type: SourceType
    name: str
    credentials: ConnectorCredentials = field(default_factory=ConnectorCredentials)
    configuration: ConnectorConfiguration = field(
        default_factory=ConnectorConfiguration
    )
    sync_state: ConnectorSyncState = field(default_factory=ConnectorSyncState)
    statistics: ConnectorStatistics = field(default_factory=ConnectorStatistics)
    enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
