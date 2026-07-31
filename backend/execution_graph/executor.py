"""Execution graph executor using dependency-aware scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.execution_graph.checkpoint import (
    ExecutionGraphCheckpoint,
    ExecutionGraphCheckpointManager,
    graph_runtime_metadata,
)
from backend.execution_graph.models import ExecutionGraph, ExecutionNode
from backend.execution_graph.scheduler import ExecutionGraphScheduler

NodeExecutor = Callable[[ExecutionNode], dict[str, Any] | None]


@dataclass(slots=True)
class ExecutionGraphExecutionResult:
    """Result payload for execution graph runs."""

    success: bool
    executed_node_ids: list[str]
    failed_node_ids: list[str]
    scheduler_metadata: dict[str, Any]
    checkpoint: dict[str, Any] | None = None

    def as_metadata(self) -> dict[str, Any]:
        """Serialize execution result deterministically."""
        return {
            "success": self.success,
            "executed_node_ids": list(self.executed_node_ids),
            "failed_node_ids": list(self.failed_node_ids),
            "scheduler_metadata": dict(self.scheduler_metadata),
            "checkpoint": dict(self.checkpoint) if self.checkpoint else None,
        }


class ExecutionGraphExecutor:
    """Execute graph nodes sequentially by default via dependency scheduler."""

    def __init__(
        self,
        graph: ExecutionGraph,
        *,
        max_parallel: int = 1,
        checkpoint_hooks: (
            dict[str, Callable[[ExecutionNode | None, dict[str, Any]], None]] | None
        ) = None,
        checkpoint_manager: ExecutionGraphCheckpointManager | None = None,
        resume_state: dict[str, Any] | None = None,
    ) -> None:
        self.graph = graph
        self.checkpoint_manager = (
            checkpoint_manager or ExecutionGraphCheckpointManager()
        )
        self.scheduler = ExecutionGraphScheduler(
            graph,
            max_parallel=max_parallel,
            checkpoint_hooks=checkpoint_hooks,
            resume_state=resume_state,
        )

    def execute(
        self,
        *,
        execute_node: NodeExecutor,
        fail_fast: bool = False,
        checkpoint_id: str | None = None,
        project_id: str | None = None,
        conversation_id: str | None = None,
        context_messages: list[str] | None = None,
    ) -> ExecutionGraphExecutionResult:
        """Execute nodes from dependency-ready queue.

        Execution is sequential by default (`max_parallel=1`) but scheduling supports
        larger ready batches for future parallel execution.
        """
        executed_node_ids: list[str] = []

        while self.scheduler.has_pending():
            batch = self.scheduler.next_ready_batch()
            if not batch:
                break

            for node in batch:
                try:
                    result = execute_node(node) or {}
                    executed_node_ids.append(node.node_id)
                    self.scheduler.mark_completed(node.node_id, metadata=result)
                except Exception as exc:  # noqa: BLE001
                    self.scheduler.mark_failed(node.node_id, error=str(exc))
                    current = self.scheduler.graph.get_node(node.node_id)
                    if (
                        fail_fast
                        and current is not None
                        and current.status.value == "failed"
                    ):
                        checkpoint = self._create_checkpoint(
                            checkpoint_id=checkpoint_id,
                            project_id=project_id,
                            conversation_id=conversation_id,
                            context_messages=context_messages,
                        )
                        scheduler_metadata = self.scheduler.metadata()
                        scheduler_metadata.update(graph_runtime_metadata(self.graph))
                        failed_node_ids = sorted(
                            scheduler_metadata["state"]["failed_nodes"]
                        )
                        return ExecutionGraphExecutionResult(
                            success=False,
                            executed_node_ids=executed_node_ids,
                            failed_node_ids=failed_node_ids,
                            scheduler_metadata=scheduler_metadata,
                            checkpoint=(
                                checkpoint.as_metadata() if checkpoint else None
                            ),
                        )

        checkpoint = self._create_checkpoint(
            checkpoint_id=checkpoint_id,
            project_id=project_id,
            conversation_id=conversation_id,
            context_messages=context_messages,
        )
        metadata = self.scheduler.metadata()
        metadata.update(graph_runtime_metadata(self.graph))
        failed_node_ids = sorted(metadata["state"]["failed_nodes"])
        success = not failed_node_ids and not self.scheduler.has_pending()
        return ExecutionGraphExecutionResult(
            success=success,
            executed_node_ids=executed_node_ids,
            failed_node_ids=failed_node_ids,
            scheduler_metadata=metadata,
            checkpoint=(checkpoint.as_metadata() if checkpoint else None),
        )

    def _create_checkpoint(
        self,
        *,
        checkpoint_id: str | None,
        project_id: str | None,
        conversation_id: str | None,
        context_messages: list[str] | None,
    ) -> ExecutionGraphCheckpoint | None:
        if not checkpoint_id:
            return None
        return self.checkpoint_manager.create_checkpoint(
            scheduler=self.scheduler,
            checkpoint_id=checkpoint_id,
            project_id=project_id,
            conversation_id=conversation_id,
            context_messages=context_messages,
            metadata={"source": "execution_graph_executor"},
        )
