"""Checkpoint models and helpers for execution graph scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.execution_graph.models import ExecutionGraph
from backend.execution_graph.scheduler import ExecutionGraphScheduler
from backend.project_memory.checkpoint import ConversationCheckpointEngine


@dataclass(slots=True)
class ExecutionGraphCheckpoint:
    """Serializable checkpoint for graph scheduler state."""

    checkpoint_id: str
    created_at: str
    scheduler_state: dict[str, Any]
    graph_metadata: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, Any]:
        """Serialize checkpoint metadata payload."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "scheduler_state": dict(self.scheduler_state),
            "graph_metadata": dict(self.graph_metadata),
            "metadata": dict(self.metadata),
        }


class ExecutionGraphCheckpointManager:
    """Persist and restore scheduler checkpoints with optional memory integration."""

    def __init__(
        self,
        checkpoint_engine: ConversationCheckpointEngine | None = None,
    ) -> None:
        self._checkpoint_engine = checkpoint_engine

    def create_checkpoint(
        self,
        *,
        scheduler: ExecutionGraphScheduler,
        checkpoint_id: str,
        project_id: str | None = None,
        conversation_id: str | None = None,
        context_messages: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionGraphCheckpoint:
        """Create scheduler checkpoint and optionally forward to project memory engine."""
        created_at = datetime.now(UTC).isoformat()
        scheduler_state = scheduler.checkpoint_state()
        graph_metadata = scheduler.graph.as_metadata()

        if (
            self._checkpoint_engine is not None
            and project_id
            and conversation_id
            and context_messages is not None
        ):
            try:
                _ = self._checkpoint_engine.create_checkpoint(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    messages=context_messages,
                )
            except Exception:  # noqa: BLE001
                # Keep checkpoint generation resilient to memory-side failures.
                pass

        return ExecutionGraphCheckpoint(
            checkpoint_id=checkpoint_id,
            created_at=created_at,
            scheduler_state=scheduler_state,
            graph_metadata=graph_metadata,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def resume_state(
        checkpoint: ExecutionGraphCheckpoint | dict[str, Any],
    ) -> dict[str, Any]:
        """Extract scheduler resume state from checkpoint payload."""
        if isinstance(checkpoint, ExecutionGraphCheckpoint):
            return dict(checkpoint.scheduler_state)
        state = checkpoint.get("scheduler_state", {})
        return state if isinstance(state, dict) else {}


def graph_runtime_metadata(graph: ExecutionGraph) -> dict[str, Any]:
    """Build runtime telemetry from graph node metadata for trace/API usage."""
    node_status: dict[str, str] = {}
    retries: dict[str, int] = {}
    queue_duration_ms: dict[str, float] = {}
    execution_duration_ms: dict[str, float] = {}
    checkpoint_state: dict[str, str] = {}

    for node in graph.nodes:
        scheduler_meta = node.metadata.get("scheduler", {})
        node_status[node.node_id] = node.status.value
        retries[node.node_id] = int(scheduler_meta.get("retry_attempts", 0))
        queue_duration_ms[node.node_id] = float(
            scheduler_meta.get("queue_duration_ms", 0.0)
        )
        execution_duration_ms[node.node_id] = float(
            scheduler_meta.get("execution_duration_ms", 0.0)
        )
        checkpoint_state[node.node_id] = str(
            scheduler_meta.get("checkpoint_state", "pending")
        )

    return {
        "node_status": node_status,
        "retries": retries,
        "queue_duration_ms": queue_duration_ms,
        "execution_duration_ms": execution_duration_ms,
        "checkpoint_state": checkpoint_state,
    }
