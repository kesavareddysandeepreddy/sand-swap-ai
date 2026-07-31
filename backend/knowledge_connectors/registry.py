"""Connector registry for connector instances keyed by source type."""

from __future__ import annotations

from collections.abc import Iterable

from backend.knowledge_connectors.base import BaseConnector
from backend.knowledge_sources.source_types import SourceType


class ConnectorRegistry:
    """Runtime registry for available connector implementations."""

    def __init__(self) -> None:
        self._connectors: dict[SourceType, BaseConnector] = {}

    def register(self, source_type: SourceType, connector: BaseConnector) -> None:
        """Register or replace connector implementation for one source type."""
        self._connectors[source_type] = connector

    def unregister(self, source_type: SourceType) -> None:
        """Remove connector implementation for source type if registered."""
        self._connectors.pop(source_type, None)

    def get(self, source_type: SourceType) -> BaseConnector:
        """Return connector for source type or raise KeyError."""
        try:
            return self._connectors[source_type]
        except KeyError as exc:
            raise KeyError(
                f"Connector for source type '{source_type.value}' not found"
            ) from exc

    def exists(self, source_type: SourceType) -> bool:
        """Return whether a connector is registered for source type."""
        return source_type in self._connectors

    def list(self) -> dict[SourceType, BaseConnector]:
        """Return a shallow copy of registered connectors."""
        return dict(self._connectors)

    def values(self) -> Iterable[BaseConnector]:
        """Return iterable over registered connector instances."""
        return self._connectors.values()
