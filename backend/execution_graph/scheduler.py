"""Dependency-aware scheduler for execution graphs."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from backend.execution_graph.models import ExecutionGraph, ExecutionNode, NodeStatus

CheckpointHook = Callable[[ExecutionNode | None, dict[str, Any]], None]


@dataclass(slots=True)
class SchedulerState:
    """State snapshot for execution graph scheduling."""

    ready_queue: list[str]
    active_nodes: list[str]
    completed_nodes: list[str]
    failed_nodes: list[str]
    retry_attempts: dict[str, int]

    def as_metadata(self) -> dict[str, Any]:
        """Serialize scheduler state deterministically."""
        return {
            "ready_queue": list(self.ready_queue),
            "active_nodes": list(self.active_nodes),
            "completed_nodes": list(self.completed_nodes),
            "failed_nodes": list(self.failed_nodes),
            "retry_attempts": dict(self.retry_attempts),
        }


class ExecutionGraphScheduler:
    """Resolve graph dependencies and yield deterministic ready-node batches."""

    def __init__(
        self,
        graph: ExecutionGraph,
        *,
        max_parallel: int = 1,
        checkpoint_hooks: dict[str, CheckpointHook] | None = None,
        resume_state: dict[str, Any] | None = None,
    ) -> None:
        errors = graph.validate()
        if errors:
            raise ValueError(
                "Invalid execution graph for scheduler: " + "; ".join(errors)
            )
        if max_parallel <= 0:
            raise ValueError("max_parallel must be greater than zero")

        self.graph = graph
        self.max_parallel = max_parallel
        self._hooks = dict(checkpoint_hooks or {})

        self._nodes_by_id = {node.node_id: node for node in graph.nodes}
        self._dependents_by_id: dict[str, list[str]] = {
            node.node_id: [] for node in graph.nodes
        }
        self._remaining_dependencies: dict[str, int] = {
            node.node_id: 0 for node in graph.nodes
        }
        for edge in graph.edges:
            self._dependents_by_id[edge.predecessor_node_id].append(
                edge.successor_node_id
            )
            self._remaining_dependencies[edge.successor_node_id] += 1

        self._ready_queue: deque[str] = deque(
            node.node_id
            for node in sorted(graph.nodes, key=lambda item: (item.order, item.node_id))
            if self._remaining_dependencies[node.node_id] == 0
        )
        self._active_nodes: set[str] = set()
        self._completed_nodes: set[str] = set()
        self._failed_nodes: set[str] = set()
        self._retry_attempts: dict[str, int] = {node.node_id: 0 for node in graph.nodes}
        now_ms = self._now_ms()
        self._queued_at_ms: dict[str, float] = {
            node_id: now_ms for node_id in self._ready_queue
        }
        self._started_at_ms: dict[str, float] = {}
        self._queue_duration_ms: dict[str, float] = {
            node.node_id: 0.0 for node in graph.nodes
        }
        self._execution_duration_ms: dict[str, float] = {
            node.node_id: 0.0 for node in graph.nodes
        }
        self._checkpoint_state: dict[str, str] = {
            node.node_id: "pending" for node in graph.nodes
        }

        if resume_state:
            self._restore_state(resume_state)

        self._emit_hook("on_scheduler_start", None, self.metadata())

    def has_pending(self) -> bool:
        """Return whether scheduler still has runnable or unresolved nodes."""
        return len(self._completed_nodes) + len(self._failed_nodes) < len(
            self.graph.nodes
        )

    def has_ready_nodes(self) -> bool:
        """Return whether one or more nodes are ready to run."""
        return bool(self._ready_queue)

    def next_ready_batch(self) -> list[ExecutionNode]:
        """Return the next deterministic ready batch, capped by max_parallel."""
        ready: list[ExecutionNode] = []
        while self._ready_queue and len(ready) < self.max_parallel:
            node_id = self._ready_queue.popleft()
            if node_id in self._completed_nodes or node_id in self._failed_nodes:
                continue
            node = self._nodes_by_id[node_id]
            now_ms = self._now_ms()
            queued_at = self._queued_at_ms.pop(node_id, now_ms)
            self._queue_duration_ms[node_id] += max(0.0, now_ms - queued_at)
            self._started_at_ms[node_id] = now_ms
            node.status = NodeStatus.RUNNING
            self._active_nodes.add(node_id)
            node.metadata.setdefault("scheduler", {})
            node.metadata["scheduler"].update(
                {
                    "queue_duration_ms": self._queue_duration_ms[node_id],
                    "execution_duration_ms": self._execution_duration_ms[node_id],
                    "retry_attempts": self._retry_attempts[node_id],
                    "checkpoint_state": self._checkpoint_state[node_id],
                    "node_status": node.status.value,
                }
            )
            ready.append(node)
            self._emit_hook("on_node_start", node, self.metadata())
        return ready

    def mark_completed(
        self,
        node_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark one node complete and unlock dependents when ready."""
        node = self._require_node(node_id)
        now_ms = self._now_ms()
        started_at = self._started_at_ms.pop(node_id, now_ms)
        self._execution_duration_ms[node_id] += max(0.0, now_ms - started_at)
        self._active_nodes.discard(node_id)
        self._completed_nodes.add(node_id)
        node.status = NodeStatus.COMPLETED
        self._checkpoint_state[node_id] = "checkpointed"
        node.metadata.setdefault("scheduler", {})
        node.metadata["scheduler"].update(
            {
                "completed": True,
                "retry_attempts": self._retry_attempts[node_id],
                "queue_duration_ms": self._queue_duration_ms[node_id],
                "execution_duration_ms": self._execution_duration_ms[node_id],
                "checkpoint_state": self._checkpoint_state[node_id],
                "node_status": node.status.value,
            }
        )
        if metadata:
            node.metadata.setdefault("result", {}).update(metadata)

        for dependent_id in sorted(self._dependents_by_id[node_id]):
            self._remaining_dependencies[dependent_id] -= 1
            if self._remaining_dependencies[dependent_id] == 0:
                self._ready_queue.append(dependent_id)
                self._queued_at_ms[dependent_id] = self._now_ms()
                dependent = self._nodes_by_id[dependent_id]
                self._emit_hook("on_node_ready", dependent, self.metadata())

        self._emit_hook("on_node_completed", node, self.metadata())
        if not self.has_pending():
            self._emit_hook("on_scheduler_finish", None, self.metadata())

    def mark_failed(
        self,
        node_id: str,
        *,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark node failure, requeue if retry policy allows, else finalize failed."""
        node = self._require_node(node_id)
        now_ms = self._now_ms()
        started_at = self._started_at_ms.pop(node_id, now_ms)
        self._execution_duration_ms[node_id] += max(0.0, now_ms - started_at)
        self._active_nodes.discard(node_id)

        attempts = self._retry_attempts[node_id] + 1
        self._retry_attempts[node_id] = attempts
        max_retries = node.retry_policy.max_retries
        should_retry = attempts <= max_retries

        node.metadata.setdefault("scheduler", {})
        node.metadata["scheduler"].update(
            {
                "retry_attempts": attempts,
                "last_error": error,
                "will_retry": should_retry,
                "queue_duration_ms": self._queue_duration_ms[node_id],
                "execution_duration_ms": self._execution_duration_ms[node_id],
            }
        )
        if metadata:
            node.metadata.setdefault("failure", {}).update(metadata)

        if should_retry:
            node.status = NodeStatus.PENDING
            self._ready_queue.append(node_id)
            self._queued_at_ms[node_id] = self._now_ms()
            self._checkpoint_state[node_id] = "pending"
            node.metadata["scheduler"]["checkpoint_state"] = self._checkpoint_state[
                node_id
            ]
            node.metadata["scheduler"]["node_status"] = node.status.value
            self._emit_hook("on_node_ready", node, self.metadata())
        else:
            node.status = NodeStatus.FAILED
            self._failed_nodes.add(node_id)
            self._checkpoint_state[node_id] = "checkpointed"
            node.metadata["scheduler"]["checkpoint_state"] = self._checkpoint_state[
                node_id
            ]
            node.metadata["scheduler"]["node_status"] = node.status.value

        self._emit_hook("on_node_failed", node, self.metadata())
        if not self.has_pending():
            self._emit_hook("on_scheduler_finish", None, self.metadata())

    def metadata(self) -> dict[str, Any]:
        """Return scheduler metadata including queue and retry state."""
        state = SchedulerState(
            ready_queue=list(self._ready_queue),
            active_nodes=sorted(self._active_nodes),
            completed_nodes=sorted(self._completed_nodes),
            failed_nodes=sorted(self._failed_nodes),
            retry_attempts=dict(self._retry_attempts),
        )
        return {
            "max_parallel": self.max_parallel,
            "retries": dict(self._retry_attempts),
            "checkpoint_state": dict(self._checkpoint_state),
            "queue_duration_ms": dict(self._queue_duration_ms),
            "execution_duration_ms": dict(self._execution_duration_ms),
            "node_status": {
                node.node_id: self._nodes_by_id[node.node_id].status.value
                for node in self.graph.nodes
            },
            "state": state.as_metadata(),
        }

    def checkpoint_state(self) -> dict[str, Any]:
        """Return serializable checkpoint state to support scheduler resume."""
        return {
            "ready_queue": list(self._ready_queue),
            "active_nodes": sorted(self._active_nodes),
            "completed_nodes": sorted(self._completed_nodes),
            "failed_nodes": sorted(self._failed_nodes),
            "retry_attempts": dict(self._retry_attempts),
            "remaining_dependencies": dict(self._remaining_dependencies),
            "queue_duration_ms": dict(self._queue_duration_ms),
            "execution_duration_ms": dict(self._execution_duration_ms),
            "checkpoint_state": dict(self._checkpoint_state),
        }

    def _emit_hook(
        self,
        hook_name: str,
        node: ExecutionNode | None,
        payload: dict[str, Any],
    ) -> None:
        hook = self._hooks.get(hook_name)
        if hook is not None:
            hook(node, payload)

    def _require_node(self, node_id: str) -> ExecutionNode:
        node = self._nodes_by_id.get(node_id)
        if node is None:
            raise KeyError(f"Unknown node_id: {node_id}")
        return node

    @staticmethod
    def _now_ms() -> float:
        return time.time() * 1000

    def _restore_state(self, state: dict[str, Any]) -> None:
        ready_queue = state.get("ready_queue")
        active_nodes = state.get("active_nodes")
        completed_nodes = state.get("completed_nodes")
        failed_nodes = state.get("failed_nodes")
        retry_attempts = state.get("retry_attempts")
        remaining_dependencies = state.get("remaining_dependencies")
        queue_duration_ms = state.get("queue_duration_ms")
        execution_duration_ms = state.get("execution_duration_ms")
        checkpoint_state = state.get("checkpoint_state")

        if isinstance(ready_queue, list):
            self._ready_queue = deque(
                [item for item in ready_queue if isinstance(item, str)]
            )
        if isinstance(active_nodes, list):
            self._active_nodes = {
                item for item in active_nodes if isinstance(item, str)
            }
        if isinstance(completed_nodes, list):
            self._completed_nodes = {
                item for item in completed_nodes if isinstance(item, str)
            }
        if isinstance(failed_nodes, list):
            self._failed_nodes = {
                item for item in failed_nodes if isinstance(item, str)
            }
        if isinstance(retry_attempts, dict):
            for node_id, attempts in retry_attempts.items():
                if node_id in self._retry_attempts and isinstance(attempts, int):
                    self._retry_attempts[node_id] = attempts
        if isinstance(remaining_dependencies, dict):
            for node_id, value in remaining_dependencies.items():
                if node_id in self._remaining_dependencies and isinstance(value, int):
                    self._remaining_dependencies[node_id] = value
        if isinstance(queue_duration_ms, dict):
            for node_id, value in queue_duration_ms.items():
                if node_id in self._queue_duration_ms and isinstance(
                    value, (int, float)
                ):
                    self._queue_duration_ms[node_id] = float(value)
        if isinstance(execution_duration_ms, dict):
            for node_id, value in execution_duration_ms.items():
                if node_id in self._execution_duration_ms and isinstance(
                    value, (int, float)
                ):
                    self._execution_duration_ms[node_id] = float(value)
        if isinstance(checkpoint_state, dict):
            for node_id, value in checkpoint_state.items():
                if node_id in self._checkpoint_state and isinstance(value, str):
                    self._checkpoint_state[node_id] = value

        now_ms = self._now_ms()
        self._queued_at_ms = {node_id: now_ms for node_id in self._ready_queue}

        for node in self.graph.nodes:
            if node.node_id in self._completed_nodes:
                node.status = NodeStatus.COMPLETED
            elif node.node_id in self._failed_nodes:
                node.status = NodeStatus.FAILED
            elif node.node_id in self._active_nodes:
                node.status = NodeStatus.RUNNING
            else:
                node.status = NodeStatus.PENDING

            node.metadata.setdefault("scheduler", {})
            node.metadata["scheduler"].update(
                {
                    "retry_attempts": self._retry_attempts[node.node_id],
                    "queue_duration_ms": self._queue_duration_ms[node.node_id],
                    "execution_duration_ms": self._execution_duration_ms[node.node_id],
                    "checkpoint_state": self._checkpoint_state[node.node_id],
                    "node_status": node.status.value,
                }
            )
