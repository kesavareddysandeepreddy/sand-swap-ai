"""Domain models for universal knowledge connector SDK infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.knowledge_connectors.sync_status import SyncStatus


@dataclass(slots=True)
class ConnectorCapabilities:
    """Describes optional behaviors supported by a connector."""

    supports_discovery: bool = True
    supports_incremental_sync: bool = True
    supports_search: bool = True
    supports_list_items: bool = True


@dataclass(slots=True)
class ConnectorConfiguration:
    """Connector runtime configuration and validation requirements."""

    required_fields: tuple[str, ...] = ()
    secret_fields: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)

    def apply_defaults(self, config: dict[str, Any] | None) -> dict[str, Any]:
        """Return config merged with defaults while preserving input values."""
        merged = dict(self.defaults)
        if config:
            merged.update(config)
        return merged

    def validate(self, config: dict[str, Any] | None) -> tuple[bool, list[str]]:
        """Validate required fields and return validation errors."""
        applied = self.apply_defaults(config)
        errors: list[str] = []
        for field_name in self.required_fields:
            value = applied.get(field_name)
            if value is None:
                errors.append(f"Missing required configuration field '{field_name}'")
                continue
            if isinstance(value, str) and not value.strip():
                errors.append(f"Configuration field '{field_name}' must not be blank")
        return (len(errors) == 0, errors)


@dataclass(slots=True)
class ConnectorMetadata:
    """Static metadata describing one connector implementation."""

    key: str
    display_name: str
    version: str = "1.0.0"
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class ConnectorHealth:
    """Connector health snapshot."""

    status: str
    connected: bool
    last_checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SyncJob:
    """Represents one connector synchronization execution."""

    connector_key: str
    source_id: str
    full_sync: bool = True
    status: SyncStatus = SyncStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items_processed: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_running(self) -> None:
        """Transition the job to running state."""
        self.status = SyncStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self.completed_at = None
        self.error = ""

    def mark_success(self, *, items_processed: int = 0) -> None:
        """Transition the job to successful completion."""
        self.status = SyncStatus.SUCCESS
        self.items_processed = max(0, items_processed)
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Transition the job to failed completion."""
        self.status = SyncStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(UTC)

    def mark_cancelled(self) -> None:
        """Transition the job to cancelled completion."""
        self.status = SyncStatus.CANCELLED
        self.completed_at = datetime.now(UTC)
