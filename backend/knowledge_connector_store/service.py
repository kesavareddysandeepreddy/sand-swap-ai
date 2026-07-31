"""Service layer for persistent connector store operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.knowledge_connector_store.models import (
    ConnectorConfiguration,
    ConnectorCredentials,
    ConnectorRecord,
    ConnectorStatistics,
)
from backend.knowledge_connector_store.repository import ConnectorStoreRepository
from backend.knowledge_sources.source_types import SourceType


class ConnectorStoreService:
    """Application service for connector persistence and startup restoration."""

    def __init__(self, *, repository: ConnectorStoreRepository) -> None:
        self._repository = repository

    def create_connector(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        name: str,
        project_id: str,
        workspace_id: str = "default",
        settings: dict[str, Any] | None = None,
        credentials_reference: str = "",
        credentials_payload: str = "",
        credentials_provider: str = "inline",
        credentials_metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> ConnectorRecord:
        """Create and persist one connector record."""
        record = ConnectorRecord(
            source_id=source_id,
            source_type=source_type,
            name=name,
            enabled=enabled,
            credentials=ConnectorCredentials(
                reference=credentials_reference,
                encrypted_payload=credentials_payload,
                provider=credentials_provider,
                metadata=credentials_metadata or {},
            ),
            configuration=ConnectorConfiguration(
                workspace_id=workspace_id,
                project_id=project_id,
                settings=settings or {},
            ),
        )
        return self._repository.create(record)

    def get_by_source_id(self, *, source_id: str) -> ConnectorRecord | None:
        """Return the first connector record linked to a knowledge source id."""
        for record in self._repository.list_all():
            if record.source_id == source_id:
                return record
        return None

    def update_connector(
        self,
        *,
        record_id: str,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
        credentials_reference: str | None = None,
        credentials_payload: str | None = None,
        credentials_provider: str | None = None,
        credentials_metadata: dict[str, Any] | None = None,
    ) -> ConnectorRecord:
        """Update mutable connector fields and persist changes."""
        record = self._require_record(record_id)
        if name is not None:
            record.name = name
        if settings is not None:
            record.configuration.settings = dict(settings)
        if credentials_reference is not None:
            record.credentials.reference = credentials_reference
        if credentials_payload is not None:
            record.credentials.encrypted_payload = credentials_payload
        if credentials_provider is not None:
            record.credentials.provider = credentials_provider
        if credentials_metadata is not None:
            record.credentials.metadata = dict(credentials_metadata)
        return self._repository.update(record)

    def delete_connector(self, *, record_id: str) -> bool:
        """Delete one persisted connector by identifier."""
        return self._repository.delete(record_id)

    def enable_connector(self, *, record_id: str) -> ConnectorRecord:
        """Enable one connector and persist state."""
        record = self._require_record(record_id)
        record.enabled = True
        return self._repository.update(record)

    def disable_connector(self, *, record_id: str) -> ConnectorRecord:
        """Disable one connector and persist state."""
        record = self._require_record(record_id)
        record.enabled = False
        return self._repository.update(record)

    def list_connectors_by_project(self, *, project_id: str) -> list[ConnectorRecord]:
        """List all connector records for one project."""
        return self._repository.list_by_project(project_id=project_id)

    def load_connectors(self) -> list[ConnectorRecord]:
        """Load all connector records for startup restoration."""
        return self._repository.list_all()

    def persist_sync_metadata(
        self,
        *,
        record_id: str,
        status: str,
        cursor: str = "",
        metadata: dict[str, Any] | None = None,
        incremental: bool = False,
    ) -> ConnectorRecord:
        """Persist synchronization metadata and cursor state."""
        record = self._require_record(record_id)
        now = datetime.now(UTC)
        record.sync_state.status = status
        record.sync_state.cursor = cursor
        record.sync_state.metadata = dict(metadata or {})
        if incremental:
            record.sync_state.last_incremental_sync_at = now
        else:
            record.sync_state.last_sync_at = now
        return self._repository.update(record)

    def persist_indexing_statistics(
        self,
        *,
        record_id: str,
        files_indexed: int,
        chunks_indexed: int,
        embeddings_indexed: int,
        errors_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ConnectorRecord:
        """Persist indexing counters and related metadata."""
        record = self._require_record(record_id)
        record.statistics = ConnectorStatistics(
            files_indexed=max(0, files_indexed),
            chunks_indexed=max(0, chunks_indexed),
            embeddings_indexed=max(0, embeddings_indexed),
            errors_count=max(0, errors_count),
            metadata=dict(metadata or {}),
        )
        return self._repository.update(record)

    def _require_record(self, record_id: str) -> ConnectorRecord:
        record = self._repository.get(record_id)
        if record is None:
            raise KeyError(f"Connector record '{record_id}' not found")
        return record
