"""Service layer for knowledge source lifecycle operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.knowledge_sources.models import KnowledgeSource
from backend.knowledge_sources.registry import ConnectorRegistry
from backend.knowledge_sources.repository import KnowledgeSourceRepository
from backend.knowledge_sources.source_types import SourceType


class KnowledgeSourceService:
    """Application service for managing project-scoped knowledge sources."""

    def __init__(
        self,
        *,
        repository: KnowledgeSourceRepository,
        connector_registry: ConnectorRegistry,
    ) -> None:
        self._repository = repository
        self._connector_registry = connector_registry

    def create_source(
        self,
        *,
        project_id: str,
        name: str,
        source_type: SourceType,
        connection_config: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> KnowledgeSource:
        """Create and persist a new knowledge source."""
        source = KnowledgeSource(
            project_id=project_id,
            name=name,
            source_type=source_type,
            connection_config=connection_config or {},
            metadata=metadata or {},
            status="configured",
        )
        workspace_id = str(source.metadata.get("workspace_id", "")).strip() or "default"
        source.connection_config = {
            **dict(source.connection_config),
            "workspace_id": workspace_id,
            "project_id": project_id,
        }
        stored = self._repository.add(source)
        self._connector_registry.manager.ensure_source_record(
            source_id=stored.id,
            source_type=stored.source_type,
            name=stored.name,
            project_id=stored.project_id,
            workspace_id=str(stored.metadata.get("workspace_id", "default")),
            settings=dict(stored.connection_config),
            enabled=stored.enabled,
        )
        return stored

    def remove_source(self, source_id: str) -> bool:
        """Remove a source."""
        return self._repository.delete(source_id)

    def list_sources(self, project_id: str) -> list[KnowledgeSource]:
        """List all sources for the project."""
        return self._repository.list(project_id)

    def enable_source(self, source_id: str) -> KnowledgeSource:
        """Enable one source and mark its status."""
        source = self._repository.enable(source_id)
        source.status = "enabled"
        workspace_id = str(source.metadata.get("workspace_id", "")).strip() or "default"
        source.connection_config = {
            **dict(source.connection_config),
            "workspace_id": workspace_id,
            "project_id": source.project_id,
        }
        self._connector_registry.manager.ensure_source_record(
            source_id=source.id,
            source_type=source.source_type,
            name=source.name,
            project_id=source.project_id,
            workspace_id=str(source.metadata.get("workspace_id", "default")),
            settings=dict(source.connection_config),
            enabled=True,
        )
        return self._repository.update(source)

    def disable_source(self, source_id: str) -> KnowledgeSource:
        """Disable one source and mark its status."""
        source = self._repository.disable(source_id)
        source.status = "disabled"
        workspace_id = str(source.metadata.get("workspace_id", "")).strip() or "default"
        source.connection_config = {
            **dict(source.connection_config),
            "workspace_id": workspace_id,
            "project_id": source.project_id,
        }
        self._connector_registry.manager.ensure_source_record(
            source_id=source.id,
            source_type=source.source_type,
            name=source.name,
            project_id=source.project_id,
            workspace_id=str(source.metadata.get("workspace_id", "default")),
            settings=dict(source.connection_config),
            enabled=False,
        )
        self._connector_registry.manager.disconnect_source(source_id=source.id)
        return self._repository.update(source)

    def configure_connector(
        self,
        *,
        source_id: str,
        connection_config: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> KnowledgeSource:
        """Persist source connector configuration and verify connectivity."""
        source = self._repository.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")

        workspace_id = str(source.metadata.get("workspace_id", "")).strip() or "default"
        effective_owner_id = (
            owner_id or str(connection_config.get("owner_id", "")).strip()
        )
        source.connection_config = {
            **dict(connection_config),
            "owner_id": effective_owner_id,
            "workspace_id": workspace_id,
            "project_id": source.project_id,
        }
        if metadata:
            source.metadata = {**source.metadata, **dict(metadata)}
            workspace_id = (
                str(source.metadata.get("workspace_id", "")).strip() or workspace_id
            )
            source.connection_config["workspace_id"] = workspace_id
            source.connection_config["owner_id"] = effective_owner_id
            source.connection_config["project_id"] = source.project_id

        self._connector_registry.manager.ensure_source_record(
            source_id=source.id,
            source_type=source.source_type,
            name=source.name,
            project_id=source.project_id,
            workspace_id=str(source.metadata.get("workspace_id", "default")),
            settings=dict(source.connection_config),
            enabled=source.enabled,
        )
        self._connector_registry.manager.connect_source(
            source_id=source.id,
            source_type=source.source_type,
            config=dict(source.connection_config),
        )
        source.status = "connected"
        return self._repository.update(source)

    def discover_connector_resources(self, *, source_id: str) -> list[dict[str, Any]]:
        """Discover source resources using persisted connector configuration."""
        source = self._repository.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")
        return self._connector_registry.manager.discover_source(
            source_id=source.id,
            source_type=source.source_type,
        )

    def sync_connector(
        self,
        *,
        source_id: str,
        incremental: bool = False,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> KnowledgeSource:
        """Run connector sync and map results into knowledge source stats."""
        source = self._repository.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")

        if incremental:
            job = self._connector_registry.manager.incremental_sync_source(
                source_id=source.id,
                source_type=source.source_type,
                owner_id=owner_id,
            )
        else:
            job = self._connector_registry.manager.sync_source(
                source_id=source.id,
                source_type=source.source_type,
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )

        source.file_count = int(job.items_processed)
        source.chunk_count = int(job.items_processed)
        source.embedding_count = int(job.items_processed)
        source.last_sync = datetime.now(UTC)
        source.status = job.status.value
        source.metadata = {
            **source.metadata,
            "last_sync_job": {
                "id": job.id,
                "status": job.status.value,
                "error": job.error,
                "metadata": dict(job.metadata),
            },
        }
        return self._repository.update(source)

    def connector_health(self, *, source_id: str) -> dict[str, Any]:
        """Return connector health for one source."""
        source = self._repository.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")
        return self._connector_registry.manager.connector_health_for_source(
            source_id=source.id,
            source_type=source.source_type,
        )

    def update_statistics(
        self,
        *,
        source_id: str,
        file_count: int,
        chunk_count: int,
        embedding_count: int,
        last_sync: datetime | None = None,
    ) -> KnowledgeSource:
        """Update source ingestion statistics."""
        source = self._repository.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")
        source.file_count = file_count
        source.chunk_count = chunk_count
        source.embedding_count = embedding_count
        source.last_sync = last_sync or datetime.now(UTC)
        source.status = "ready" if source.enabled else "disabled"
        return self._repository.update(source)

    def health(self) -> dict[str, object]:
        """Return health metadata for the knowledge source subsystem."""
        connectors = self._connector_registry.list_connectors()
        connector_statuses: dict[str, str] = {}
        for source_type, connector in connectors.items():
            if hasattr(connector, "health"):
                connector_health = connector.health()
                connector_statuses[source_type.value] = connector_health.status
            else:
                connector_statuses[source_type.value] = str(
                    getattr(connector, "status", "unknown")
                )
        return {
            "status": "ok",
            "connectors_total": len(connectors),
            "connectors": connector_statuses,
        }
