"""Sync status enumeration for connector synchronization jobs."""

from __future__ import annotations

from enum import StrEnum


class SyncStatus(StrEnum):
    """Lifecycle states for a connector synchronization job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
