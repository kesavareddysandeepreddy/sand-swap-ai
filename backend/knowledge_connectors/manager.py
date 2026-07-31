"""Connector manager for connector registration, lookup, health and sync orchestration."""

from __future__ import annotations

import logging
from typing import Any

import requests

from backend.knowledge_connector_store.service import ConnectorStoreService
from backend.knowledge_connectors.base import BaseConnector
from backend.knowledge_connectors.factory import ConnectorBuilder, ConnectorFactory
from backend.knowledge_connectors.github_connector import GitHubConnector
from backend.knowledge_connectors.models import ConnectorHealth, SyncJob
from backend.knowledge_connectors.registry import ConnectorRegistry
from backend.knowledge_sources.source_types import SourceType


class ConnectorManager:
    """Coordinates connector lifecycle across factory and registry."""

    def __init__(
        self,
        *,
        registry: ConnectorRegistry,
        factory: ConnectorFactory,
        store_service: ConnectorStoreService,
    ) -> None:
        self._registry = registry
        self._factory = factory
        self._store_service = store_service
        self._logger = logging.getLogger(__name__)
        self._record_id_by_source_type: dict[SourceType, str] = {}
        self._record_id_by_source_id: dict[str, str] = {}
        self._source_type_by_source_id: dict[str, SourceType] = {}

    def register_connector(
        self,
        source_type: SourceType,
        builder: ConnectorBuilder,
    ) -> BaseConnector:
        """Register builder and eagerly construct one runtime instance."""
        self._factory.register_builder(source_type, builder)
        connector = self._factory.create(source_type)
        self._registry.register(source_type, connector)
        return connector

    def bootstrap_default_connector(
        self,
        *,
        source_type: SourceType,
        name: str,
        project_id: str,
        workspace_id: str,
        settings: dict[str, Any],
        source_id: str,
        builder: ConnectorBuilder,
    ) -> BaseConnector:
        """Ensure one connector exists in store and runtime during startup."""
        existing = [
            record
            for record in self._store_service.load_connectors()
            if record.source_type == source_type
            and record.configuration.project_id == project_id
            and record.configuration.workspace_id == workspace_id
        ]
        if existing:
            record = existing[0]
        else:
            record = self._store_service.create_connector(
                source_id=source_id,
                source_type=source_type,
                name=name,
                project_id=project_id,
                workspace_id=workspace_id,
                settings=settings,
                enabled=True,
            )
        self._record_id_by_source_id[source_id] = record.id
        self._source_type_by_source_id[source_id] = source_type
        self._record_id_by_source_type[source_type] = record.id
        connector = self.register_connector(source_type, builder)
        if record.enabled:
            connector.connect(config=record.configuration.settings)
        else:
            connector.disconnect()
        return connector

    def restore_connectors(self) -> None:
        """Restore enabled connectors from persisted store on startup."""
        for record in self._store_service.load_connectors():
            self._record_id_by_source_type[record.source_type] = record.id
            self._record_id_by_source_id[record.source_id] = record.id
            self._source_type_by_source_id[record.source_id] = record.source_type
            if not self._factory.has_builder(record.source_type):
                continue
            connector = self.get_connector(record.source_type)
            if record.enabled:
                try:
                    connector.connect(config=record.configuration.settings)
                except ValueError:
                    # Keep startup resilient when a connector requires credentials
                    # that are not configured yet for this persisted source.
                    connector.disconnect()
                except requests.HTTPError as exc:
                    if isinstance(connector, GitHubConnector):
                        connector.mark_authentication_failed(detail=str(exc))
                    else:
                        connector.disconnect()
                    self._logger.warning(
                        "Connector restore HTTP error for source_id=%s; marked as failed and continuing startup. Error: %s",
                        record.source_id,
                        exc,
                    )
                except requests.exceptions.RequestException as exc:
                    if isinstance(connector, GitHubConnector):
                        connector.mark_authentication_failed(detail=str(exc))
                    else:
                        connector.disconnect()
                    self._logger.warning(
                        "Connector restore network error for source_id=%s; marked as offline and continuing startup. Error: %s",
                        record.source_id,
                        exc,
                    )
                except Exception as exc:  # noqa: BLE001
                    if isinstance(connector, GitHubConnector):
                        connector.mark_authentication_failed(detail=str(exc))
                    else:
                        connector.disconnect()
                    self._logger.error(
                        "Connector restore unexpected error for source_id=%s; marked as failed and continuing startup.",
                        record.source_id,
                        exc_info=True,
                    )
            else:
                connector.disconnect()

    def get_connector(self, source_type: SourceType) -> BaseConnector:
        """Resolve connector from registry, lazily constructing when needed."""
        if self._registry.exists(source_type):
            return self._registry.get(source_type)
        connector = self._factory.create(source_type)
        self._registry.register(source_type, connector)
        return connector

    def has_connector(self, source_type: SourceType) -> bool:
        """Return whether source type has a registered connector builder."""
        return self._factory.has_builder(source_type)

    def list_connectors(self) -> dict[SourceType, BaseConnector]:
        """Return current connector instance map."""
        return self._registry.list()

    def health(self) -> dict[SourceType, ConnectorHealth]:
        """Collect connector health snapshots by source type."""
        return {
            source_type: connector.health()
            for source_type, connector in self._registry.list().items()
        }

    def validate(
        self,
        *,
        source_type: SourceType,
        config: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Validate configuration for one connector type."""
        connector = self.get_connector(source_type)
        return connector.validate(config=config)

    def sync(
        self,
        *,
        source_type: SourceType,
        config: dict[str, Any],
        source_id: str,
    ) -> SyncJob:
        """Run full sync for one connector type."""
        connector = self.get_connector(source_type)
        job = connector.sync(config=config, source_id=source_id)
        self._persist_sync_state(
            source_type=source_type,
            config=config,
            job=job,
            incremental=False,
        )
        return job

    def incremental_sync(
        self,
        *,
        source_type: SourceType,
        config: dict[str, Any],
        source_id: str,
        cursor: str | None = None,
    ) -> SyncJob:
        """Run incremental sync for one connector type."""
        connector = self.get_connector(source_type)
        job = connector.incremental_sync(
            config=config,
            source_id=source_id,
            cursor=cursor,
        )
        self._persist_sync_state(
            source_type=source_type,
            config=config,
            job=job,
            incremental=True,
        )
        return job

    def _persist_sync_state(
        self,
        *,
        source_type: SourceType,
        config: dict[str, Any],
        job: SyncJob,
        incremental: bool,
    ) -> None:
        record_id = self._record_id_by_source_type.get(source_type)
        if record_id is None:
            return
        sync_metadata = {
            "sync_job_id": job.id,
            "items_processed": int(job.items_processed),
            "sync_metadata": dict(job.metadata),
        }
        self._store_service.persist_sync_metadata(
            record_id=record_id,
            status=job.status.value,
            cursor=str(config.get("cursor", "")),
            metadata=sync_metadata,
            incremental=incremental,
        )
        self._store_service.persist_indexing_statistics(
            record_id=record_id,
            files_indexed=int(job.items_processed),
            chunks_indexed=int(job.items_processed),
            embeddings_indexed=int(job.items_processed),
            errors_count=0 if not job.error else 1,
            metadata={"connector": source_type.value},
        )

    def ensure_source_record(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        name: str,
        project_id: str,
        workspace_id: str,
        settings: dict[str, Any],
        enabled: bool,
    ) -> None:
        """Ensure a connector-store record exists for one knowledge source."""
        existing = self._store_service.get_by_source_id(source_id=source_id)
        if existing is None:
            created = self._store_service.create_connector(
                source_id=source_id,
                source_type=source_type,
                name=name,
                project_id=project_id,
                workspace_id=workspace_id,
                settings=settings,
                enabled=enabled,
            )
            self._record_id_by_source_id[source_id] = created.id
            self._record_id_by_source_type[source_type] = created.id
            self._source_type_by_source_id[source_id] = source_type
            return

        updated = self._store_service.update_connector(
            record_id=existing.id,
            name=name,
            settings=settings,
        )
        if enabled:
            updated = self._store_service.enable_connector(record_id=updated.id)
        else:
            updated = self._store_service.disable_connector(record_id=updated.id)
        self._record_id_by_source_id[source_id] = updated.id
        self._record_id_by_source_type[source_type] = updated.id
        self._source_type_by_source_id[source_id] = source_type

    def connect_source(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        config: dict[str, Any],
    ) -> bool:
        """Connect one source and persist associated credentials/configuration."""
        connector = self.get_connector(source_type)
        connected = connector.connect(config=config)
        self._persist_source_config(
            source_id=source_id, source_type=source_type, config=config
        )
        return connected

    def disconnect_source(self, *, source_id: str) -> None:
        """Disconnect one source connector if a runtime connector exists."""
        source_type = self._source_type_by_source_id.get(source_id)
        if source_type is None:
            return
        if not self.has_connector(source_type):
            return
        connector = self.get_connector(source_type)
        connector.disconnect()

    def discover_source(
        self, *, source_id: str, source_type: SourceType
    ) -> list[dict[str, Any]]:
        """Discover resources for a source using persisted connector config."""
        connector = self.get_connector(source_type)
        config = self._load_source_config(source_id=source_id)
        return connector.discover(config=config)

    def search_source(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search source resources using persisted connector config."""
        connector = self.get_connector(source_type)
        config = self._load_source_config(source_id=source_id)
        return connector.search(config=config, query=query, limit=limit)

    def list_source_items(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        """List source items using persisted connector config."""
        connector = self.get_connector(source_type)
        config = self._load_source_config(source_id=source_id)
        return connector.list_items(config=config, page_size=page_size, cursor=cursor)

    def sync_source(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> SyncJob:
        """Run full sync for one source using persisted config."""
        config = self._load_source_config(source_id=source_id)
        # Inject authenticated identity so chunk metadata is correct
        if owner_id:
            config["owner_id"] = owner_id
        if workspace_id:
            config["workspace_id"] = workspace_id
        if project_id:
            config["project_id"] = project_id
        self._logger.debug(
            "SYNC_SOURCE_CONFIG source_id=%s owner_id=%s workspace_id=%s project_id=%s",
            source_id,
            config.get("owner_id", ""),
            config.get("workspace_id", ""),
            config.get("project_id", ""),
        )
        return self.sync(source_type=source_type, config=config, source_id=source_id)

    def incremental_sync_source(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        owner_id: str | None = None,
        cursor: str | None = None,
    ) -> SyncJob:
        """Run incremental sync for one source using persisted config."""
        config = self._load_source_config(source_id=source_id)
        if owner_id:
            config["owner_id"] = owner_id
        if cursor is not None:
            config = dict(config)
            config["cursor"] = cursor
        return self.incremental_sync(
            source_type=source_type,
            config=config,
            source_id=source_id,
            cursor=cursor,
        )

    def connector_health_for_source(
        self, *, source_id: str, source_type: SourceType
    ) -> dict[str, Any]:
        """Return health payload for one source connector."""
        connector = self.get_connector(source_type)
        health = connector.health()
        return {
            "status": health.status,
            "connected": health.connected,
            "message": health.message,
            "details": dict(health.details),
        }

    def _persist_source_config(
        self,
        *,
        source_id: str,
        source_type: SourceType,
        config: dict[str, Any],
    ) -> None:
        record = self._store_service.get_by_source_id(source_id=source_id)
        if record is None:
            return
        credentials_payload = ""
        credentials_provider = "inline"
        credentials_reference = ""
        credentials_metadata: dict[str, Any] = {}
        if source_type == SourceType.GITHUB:
            token = str(config.get("token", "")).strip()
            if token:
                credentials_payload = token
                credentials_provider = "github_pat"
                credentials_reference = f"github://{source_id}"
        elif source_type == SourceType.SHAREPOINT:
            token = str(config.get("access_token", "")).strip()
            tenant_id = str(config.get("tenant_id", "")).strip()
            if token:
                credentials_payload = token
                credentials_provider = "microsoft_graph"
                credentials_reference = f"sharepoint://{tenant_id or source_id}"
                credentials_metadata = {"tenant_id": tenant_id}

        self._store_service.update_connector(
            record_id=record.id,
            settings=dict(config),
            credentials_payload=credentials_payload,
            credentials_provider=credentials_provider,
            credentials_reference=credentials_reference,
            credentials_metadata=credentials_metadata,
        )

    def _load_source_config(self, *, source_id: str) -> dict[str, Any]:
        record = self._store_service.get_by_source_id(source_id=source_id)
        if record is None:
            return {}
        config = dict(record.configuration.settings)
        config.setdefault("workspace_id", record.configuration.workspace_id)
        config.setdefault("project_id", record.configuration.project_id)
        if record.source_type == SourceType.GITHUB:
            token_aliases = (
                "token",
                "personal_access_token",
                "github_token",
                "pat",
            )
            token_from_settings = ""
            for alias in token_aliases:
                value = str(config.get(alias, "")).strip()
                if value:
                    token_from_settings = value
                    break

            token_from_credentials = str(record.credentials.encrypted_payload).strip()
            normalized_token = token_from_credentials or token_from_settings
            if normalized_token:
                config["token"] = normalized_token
        if (
            record.source_type == SourceType.SHAREPOINT
            and record.credentials.encrypted_payload
        ):
            config.setdefault("access_token", record.credentials.encrypted_payload)
            tenant_id = str(record.credentials.metadata.get("tenant_id", "")).strip()
            if tenant_id:
                config.setdefault("tenant_id", tenant_id)
        return config
