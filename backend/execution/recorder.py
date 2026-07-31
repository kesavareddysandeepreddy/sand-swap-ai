"""In-memory execution trace recorder."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.execution.models import ExecutionTrace


class ExecutionRecorder:
    """Store and retrieve execution traces in memory."""

    def __init__(self) -> None:
        self._traces: dict[str, ExecutionTrace] = {}
        self._order: list[str] = []

    def create_trace(self, worker_name: str, request_id: str | None) -> ExecutionTrace:
        """Create and store a new trace."""
        trace = ExecutionTrace(
            trace_id=str(uuid4()),
            worker_name=worker_name,
            request_id=request_id,
            started_at=datetime.now(UTC),
            metadata={},
        )
        self._traces[trace.trace_id] = trace
        self._order.append(trace.trace_id)
        return trace

    def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        """Resolve one trace by id."""
        return self._traces.get(trace_id)

    def list_recent(self, limit: int) -> list[ExecutionTrace]:
        """Return most recently created traces first."""
        if limit <= 0:
            return []
        recent_ids = list(reversed(self._order))[:limit]
        return [self._traces[trace_id] for trace_id in recent_ids]

    def clear(self) -> None:
        """Remove all traces from memory."""
        self._traces.clear()
        self._order.clear()
