"""Factory for constructing connector instances by source type."""

from __future__ import annotations

from collections.abc import Callable

from backend.knowledge_connectors.base import BaseConnector
from backend.knowledge_sources.source_types import SourceType

ConnectorBuilder = Callable[[], BaseConnector]


class ConnectorFactory:
    """Factory that maps source types to connector builders."""

    def __init__(self) -> None:
        self._builders: dict[SourceType, ConnectorBuilder] = {}

    def register_builder(
        self, source_type: SourceType, builder: ConnectorBuilder
    ) -> None:
        """Register connector builder for one source type."""
        self._builders[source_type] = builder

    def has_builder(self, source_type: SourceType) -> bool:
        """Return whether a builder exists for source type."""
        return source_type in self._builders

    def create(self, source_type: SourceType) -> BaseConnector:
        """Instantiate connector for source type or raise KeyError."""
        try:
            builder = self._builders[source_type]
        except KeyError as exc:
            raise KeyError(
                f"Connector builder for source type '{source_type.value}' not found"
            ) from exc
        return builder()

    def list_builders(self) -> dict[SourceType, ConnectorBuilder]:
        """Return a shallow copy of registered builders."""
        return dict(self._builders)
