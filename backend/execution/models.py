"""Execution trace models for internal worker orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

ExecutionStepStatus = Literal["pending", "running", "completed", "failed", "skipped"]


@dataclass(slots=True)
class ExecutionStep:
    """Represents one stage in a worker execution trace."""

    id: str
    stage: str
    status: ExecutionStepStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionTrace:
    """Represents one end-to-end worker execution trace."""

    trace_id: str
    worker_name: str
    request_id: str | None
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    steps: list[ExecutionStep] = field(default_factory=list)

    def add_step(
        self, stage: str, metadata: dict[str, Any] | None = None
    ) -> ExecutionStep:
        """Create and append a running step to the trace."""
        step = ExecutionStep(
            id=str(uuid4()),
            stage=stage,
            status="running",
            started_at=datetime.now(UTC),
            metadata=dict(metadata or {}),
        )
        self.steps.append(step)
        return step

    def complete_step(
        self,
        step_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionStep:
        """Mark the provided step as completed."""
        step = self._get_step(step_id)
        step.completed_at = datetime.now(UTC)
        step.status = "completed"
        if step.started_at is not None and step.completed_at is not None:
            step.duration_ms = (
                step.completed_at - step.started_at
            ).total_seconds() * 1000
        if metadata:
            step.metadata.update(metadata)
        return step

    def fail_step(
        self,
        step_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionStep:
        """Mark the provided step as failed."""
        step = self._get_step(step_id)
        step.completed_at = datetime.now(UTC)
        step.status = "failed"
        if step.started_at is not None and step.completed_at is not None:
            step.duration_ms = (
                step.completed_at - step.started_at
            ).total_seconds() * 1000
        if metadata:
            step.metadata.update(metadata)
        return step

    def finish(self) -> None:
        """Mark the full trace as completed."""
        self.completed_at = datetime.now(UTC)
        self.total_duration_ms = (
            self.completed_at - self.started_at
        ).total_seconds() * 1000

    def _get_step(self, step_id: str) -> ExecutionStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"Unknown step id: {step_id}")
