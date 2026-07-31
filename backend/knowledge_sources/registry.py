"""Connector registry adapter for knowledge source types."""

from __future__ import annotations

from backend.knowledge_connector_store.service import ConnectorStoreService
from backend.knowledge_connectors.factory import ConnectorFactory
from backend.knowledge_connectors.github_connector import GitHubConnector
from backend.knowledge_connectors.manager import ConnectorManager
from backend.knowledge_connectors.registry import (
    ConnectorRegistry as SDKConnectorRegistry,
)
from backend.knowledge_connectors.sharepoint_connector import SharePointConnector
from backend.knowledge_connectors.upload_connector import UploadConnector
from backend.knowledge_sources.source_types import SourceType
from backend.rag.application.document_service import DocumentIngestionService
from backend.upload_manager.service import UploadManagerService


class ConnectorRegistry:
    """Compatibility registry that proxies to the universal connector SDK."""

    def __init__(
        self,
        *,
        upload_manager: UploadManagerService,
        ingestion_service: DocumentIngestionService,
        store_service: ConnectorStoreService,
    ) -> None:
        self._registry = SDKConnectorRegistry()
        self._factory = ConnectorFactory()
        self._manager = ConnectorManager(
            registry=self._registry,
            factory=self._factory,
            store_service=store_service,
        )
        self._manager.bootstrap_default_connector(
            source_type=SourceType.UPLOAD,
            name="Upload Connector",
            project_id="default",
            workspace_id="default",
            settings={},
            source_id="upload-default",
            builder=lambda: UploadConnector(upload_manager=upload_manager),
        )
        self._manager.register_connector(
            SourceType.GITHUB,
            lambda: GitHubConnector(ingestion_service=ingestion_service),
        )
        self._manager.register_connector(
            SourceType.SHAREPOINT,
            lambda: SharePointConnector(ingestion_service=ingestion_service),
        )
        self._manager.restore_connectors()

    @property
    def manager(self) -> ConnectorManager:
        """Expose connector manager for orchestration use-cases."""
        return self._manager

    def get_connector(self, source_type: SourceType):
        """Return connector when registered, otherwise compatibility placeholder."""
        if self._manager.has_connector(source_type):
            return self._manager.get_connector(source_type)
        return _PlaceholderConnector(source_type=source_type)

    def list_connectors(self) -> dict[SourceType, object]:
        """Return all source types with registered connectors or placeholders."""
        connectors: dict[SourceType, object] = {
            source_type: _PlaceholderConnector(source_type=source_type)
            for source_type in SourceType
        }
        connectors.update(self._manager.list_connectors())
        return connectors


class _PlaceholderConnector:
    """Compatibility adapter for source types without concrete SDK connectors."""

    def __init__(self, *, source_type: SourceType) -> None:
        self.source_type = source_type
        self.name = f"{source_type.value}Connector"
        self.status = "not_implemented"
