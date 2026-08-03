"""Workflow run and message entities for orchestration runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class WorkflowRunStatus(StrEnum):
    """Lifecycle states for workflow execution."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class NodeExecutionStatus(StrEnum):
    """Lifecycle states for each node execution record."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class AgentMessage:
    """Structured inter-agent communication event."""

    sender: str
    receiver: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NodeExecutionRecord:
    """Node execution state persisted for run history."""

    node_id: str
    node_name: str
    node_type: str
    status: str = NodeExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0
    error: str = ""
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRun:
    """Persisted execution run for one workflow."""

    id: str = field(default_factory=lambda: str(uuid4()))
    workflow_id: str = ""
    status: str = WorkflowRunStatus.QUEUED
    input_payload: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: float = 0.0
    error: str = ""
    current_node_id: str = ""
    pending_node_id: str = ""
    cancel_requested: bool = False
    node_records: list[NodeExecutionRecord] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        """Refresh modification timestamp."""
        self.updated_at = datetime.now(UTC)
