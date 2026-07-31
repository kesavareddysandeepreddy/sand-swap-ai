"""Base connector abstraction for the universal connector SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.knowledge_connectors.models import (
    ConnectorCapabilities,
    ConnectorConfiguration,
    ConnectorHealth,
    ConnectorMetadata,
    SyncJob,
)


class BaseConnector(ABC):
    """Contract implemented by every external knowledge connector."""

    metadata: ConnectorMetadata
    capabilities: ConnectorCapabilities
    configuration: ConnectorConfiguration

    def __init__(
        self,
        *,
        metadata: ConnectorMetadata,
        capabilities: ConnectorCapabilities,
        configuration: ConnectorConfiguration,
    ) -> None:
        self.metadata = metadata
        self.capabilities = capabilities
        self.configuration = configuration

    @abstractmethod
    def connect(self, *, config: dict[str, Any]) -> bool:
        """Establish connector session and return whether connected."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release connector resources and session state."""

    @abstractmethod
    def validate(self, *, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate connector-specific configuration payload."""

    @abstractmethod
    def discover(self, *, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Discover source entities available for synchronization."""

    @abstractmethod
    def sync(self, *, config: dict[str, Any], source_id: str) -> SyncJob:
        """Run a full synchronization for a knowledge source."""

    @abstractmethod
    def incremental_sync(
        self,
        *,
        config: dict[str, Any],
        source_id: str,
        cursor: str | None = None,
    ) -> SyncJob:
        """Run an incremental synchronization for a knowledge source."""

    @abstractmethod
    def health(self) -> ConnectorHealth:
        """Return current connector health status."""

    @abstractmethod
    def search(
        self,
        *,
        config: dict[str, Any],
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search connector items using provider-native semantics."""

    @abstractmethod
    def list_items(
        self,
        *,
        config: dict[str, Any],
        page_size: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        """List connector items for browse/sync pipelines."""
