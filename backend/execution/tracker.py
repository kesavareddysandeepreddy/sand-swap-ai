"""Execution tracker context manager utilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from backend.execution.models import ExecutionTrace


class ExecutionTracker:
    """Context-manager tracker for recording step lifecycle."""

    def __init__(self, trace: ExecutionTrace) -> None:
        self.trace = trace

    @contextmanager
    def step(
        self, stage: str, metadata: dict[str, object] | None = None
    ) -> Iterator[None]:
        """Track one execution stage with automatic completion/failure."""
        step = self.trace.add_step(stage=stage, metadata=dict(metadata or {}))
        try:
            yield
        except Exception as exc:  # noqa: BLE001
            self.trace.fail_step(
                step.id,
                metadata={"error": str(exc), "exception_type": type(exc).__name__},
            )
            raise
        else:
            self.trace.complete_step(step.id)
