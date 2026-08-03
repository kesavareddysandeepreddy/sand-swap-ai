"""Execution engine for multi-agent orchestration workflows."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import RLock
from time import perf_counter
from typing import Any, Callable

from backend.agent_orchestration.domain.run import (
    AgentMessage,
    NodeExecutionRecord,
    NodeExecutionStatus,
    WorkflowRun,
    WorkflowRunStatus,
)
from backend.agent_orchestration.domain.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)
from backend.agent_orchestration.events import (
    WORKFLOW_FINISHED,
    WORKFLOW_NODE_COMPLETED,
    WORKFLOW_NODE_FAILED,
    WORKFLOW_NODE_STARTED,
)

AgentEvaluator = Callable[[WorkflowNode, dict[str, Any]], dict[str, Any]]


class WorkflowExecutionEngine:
    """Executes workflow graphs with support for parallel branches and loops."""

    def __init__(self, *, max_parallel_workers: int = 4) -> None:
        self._max_parallel_workers = max_parallel_workers
        self._lock = RLock()

    def execute(
        self,
        *,
        workflow: Workflow,
        run: WorkflowRun,
        agent_evaluator: AgentEvaluator,
        should_cancel: Callable[[str], bool],
        start_node_ids: list[str] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow and return updated run state."""
        started = perf_counter()
        run.status = WorkflowRunStatus.RUNNING
        if run.started_at is None:
            run.started_at = datetime.now(UTC)
        run.current_node_id = ""
        run.error = ""
        run.logs.append(
            self._log_event(
                WORKFLOW_NODE_STARTED,
                "Workflow execution started",
                {"workflow_id": workflow.id, "run_id": run.id},
            )
        )

        node_map = {node.id: node for node in workflow.nodes}
        edge_map = self._edge_map(workflow.edges)
        incoming = self._incoming_map(workflow.edges)
        merge_counters: dict[str, int] = defaultdict(int)
        loop_counters: dict[str, int] = defaultdict(int)

        pending_nodes: list[str] = list(start_node_ids or [])
        if not pending_nodes:
            start_node = next(
                (node for node in workflow.nodes if node.node_type == "Start"),
                None,
            )
            if start_node is None:
                run.status = WorkflowRunStatus.FAILED
                run.error = "Missing Start node"
                return self._finalize_run(run, started)
            pending_nodes = [start_node.id]
        while pending_nodes:
            if should_cancel(run.id):
                run.status = WorkflowRunStatus.CANCELED
                run.error = "Execution canceled"
                return self._finalize_run(run, started)

            batch = list(dict.fromkeys(pending_nodes))
            pending_nodes = []
            results = self._execute_batch(
                batch=batch,
                node_map=node_map,
                edge_map=edge_map,
                incoming=incoming,
                merge_counters=merge_counters,
                loop_counters=loop_counters,
                run=run,
                agent_evaluator=agent_evaluator,
            )
            for result in results:
                if result["status"] == "pause":
                    run.status = WorkflowRunStatus.WAITING_APPROVAL
                    run.pending_node_id = str(result["node_id"])
                    run.current_node_id = str(result["node_id"])
                    run.touch()
                    return self._finalize_run(run, started, completed=False)
                if result["status"] == "error":
                    run.status = WorkflowRunStatus.FAILED
                    run.error = str(result.get("error", "Unknown node execution error"))
                    return self._finalize_run(run, started)
                next_ids = list(result.get("next_nodes", []))
                pending_nodes.extend(next_ids)

        if run.status not in {
            WorkflowRunStatus.CANCELED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.WAITING_APPROVAL,
        }:
            run.status = WorkflowRunStatus.SUCCEEDED
        return self._finalize_run(run, started)

    def resume_after_approval(
        self,
        *,
        workflow: Workflow,
        run: WorkflowRun,
        approval_action: str,
        edited_input: dict[str, Any],
        should_cancel: Callable[[str], bool],
    ) -> WorkflowRun:
        """Resume a run paused at human approval node."""
        if run.status != WorkflowRunStatus.WAITING_APPROVAL or not run.pending_node_id:
            return run

        action = approval_action.strip().lower()
        if action == "reject":
            run.status = WorkflowRunStatus.CANCELED
            run.error = "Execution rejected by user"
            run.pending_node_id = ""
            run.touch()
            return run

        if action == "cancel":
            run.status = WorkflowRunStatus.CANCELED
            run.error = "Execution canceled by user"
            run.pending_node_id = ""
            run.touch()
            return run

        if action == "edit":
            run.context["edited_input"] = dict(edited_input)

        node_map = {node.id: node for node in workflow.nodes}
        edge_map = self._edge_map(workflow.edges)
        pending_node = node_map.get(run.pending_node_id)
        if pending_node is None:
            run.status = WorkflowRunStatus.FAILED
            run.error = "Pending approval node not found"
            run.pending_node_id = ""
            run.touch()
            return run

        run.pending_node_id = ""
        run.status = WorkflowRunStatus.RUNNING
        next_nodes = [edge.target_node_id for edge in edge_map.get(pending_node.id, [])]
        for node_id in next_nodes:
            if should_cancel(run.id):
                run.status = WorkflowRunStatus.CANCELED
                run.error = "Execution canceled"
                break
            run.current_node_id = node_id
        run.touch()
        return run

    def _execute_batch(
        self,
        *,
        batch: list[str],
        node_map: dict[str, WorkflowNode],
        edge_map: dict[str, list[WorkflowEdge]],
        incoming: dict[str, list[str]],
        merge_counters: dict[str, int],
        loop_counters: dict[str, int],
        run: WorkflowRun,
        agent_evaluator: AgentEvaluator,
    ) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(
            max_workers=min(self._max_parallel_workers, max(1, len(batch)))
        ) as executor:
            futures = [
                executor.submit(
                    self._execute_node,
                    node_id,
                    node_map,
                    edge_map,
                    incoming,
                    merge_counters,
                    loop_counters,
                    run,
                    agent_evaluator,
                )
                for node_id in batch
            ]
            return [future.result() for future in futures]

    def _execute_node(
        self,
        node_id: str,
        node_map: dict[str, WorkflowNode],
        edge_map: dict[str, list[WorkflowEdge]],
        incoming: dict[str, list[str]],
        merge_counters: dict[str, int],
        loop_counters: dict[str, int],
        run: WorkflowRun,
        agent_evaluator: AgentEvaluator,
    ) -> dict[str, Any]:
        node = node_map.get(node_id)
        if node is None:
            return {"status": "error", "node_id": node_id, "error": "Node not found"}

        start_at = perf_counter()
        record = self._ensure_record(run, node)
        record.status = NodeExecutionStatus.RUNNING
        record.started_at = datetime.now(UTC)
        run.current_node_id = node.id
        run.logs.append(
            self._log_event(
                WORKFLOW_NODE_STARTED,
                f"Node started: {node.name}",
                {"node_id": node.id, "node_type": node.node_type},
            )
        )

        try:
            next_nodes = self._next_nodes_for(
                node=node,
                edge_map=edge_map,
                incoming=incoming,
                merge_counters=merge_counters,
                loop_counters=loop_counters,
                run=run,
                agent_evaluator=agent_evaluator,
            )
            duration_ms = round((perf_counter() - start_at) * 1000, 3)
            record.status = NodeExecutionStatus.COMPLETED
            record.completed_at = datetime.now(UTC)
            record.duration_ms = duration_ms
            run.logs.append(
                self._log_event(
                    WORKFLOW_NODE_COMPLETED,
                    f"Node completed: {node.name}",
                    {
                        "node_id": node.id,
                        "node_type": node.node_type,
                        "duration_ms": duration_ms,
                    },
                )
            )
            if node.node_type == "Human Approval":
                auto_approve = bool(node.config.get("auto_approve", False))
                if not auto_approve:
                    return {"status": "pause", "node_id": node.id, "next_nodes": []}
            if node.node_type == "End":
                return {"status": "ok", "node_id": node.id, "next_nodes": []}
            return {"status": "ok", "node_id": node.id, "next_nodes": next_nodes}
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((perf_counter() - start_at) * 1000, 3)
            record.status = NodeExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.duration_ms = duration_ms
            record.error = str(exc)
            run.logs.append(
                self._log_event(
                    WORKFLOW_NODE_FAILED,
                    f"Node failed: {node.name}",
                    {
                        "node_id": node.id,
                        "node_type": node.node_type,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                )
            )
            return {"status": "error", "node_id": node.id, "error": str(exc)}

    def _next_nodes_for(
        self,
        *,
        node: WorkflowNode,
        edge_map: dict[str, list[WorkflowEdge]],
        incoming: dict[str, list[str]],
        merge_counters: dict[str, int],
        loop_counters: dict[str, int],
        run: WorkflowRun,
        agent_evaluator: AgentEvaluator,
    ) -> list[str]:
        outgoing = edge_map.get(node.id, [])

        if node.node_type == "Condition":
            field_name = str(node.config.get("field", ""))
            operator = str(node.config.get("operator", "equals")).lower()
            expected_value = node.config.get("value")
            current_value = run.context.get(field_name)
            matched = self._compare(current_value, expected_value, operator)
            target_condition = "true" if matched else "false"
            for edge in outgoing:
                if edge.condition.strip().lower() == target_condition:
                    return [edge.target_node_id]
            return [edge.target_node_id for edge in outgoing[:1]]

        if node.node_type == "Parallel Split":
            return [edge.target_node_id for edge in outgoing]

        if node.node_type == "Merge":
            merge_counters[node.id] += 1
            required = len(incoming.get(node.id, []))
            if merge_counters[node.id] < max(1, required):
                return []
            merge_counters[node.id] = 0
            return [edge.target_node_id for edge in outgoing[:1]]

        if node.node_type == "Loop":
            max_loops = int(node.config.get("max_loops", 1))
            loop_counters[node.id] += 1
            if loop_counters[node.id] <= max_loops:
                loop_edge = next(
                    (
                        edge
                        for edge in outgoing
                        if edge.condition.strip().lower() == "loop"
                    ),
                    None,
                )
                if loop_edge:
                    return [loop_edge.target_node_id]
            exit_edge = next(
                (
                    edge
                    for edge in outgoing
                    if edge.condition.strip().lower() in {"exit", "done"}
                ),
                None,
            )
            if exit_edge:
                return [exit_edge.target_node_id]
            return [edge.target_node_id for edge in outgoing[:1]]

        if node.node_type == "Agent":
            agent_output = agent_evaluator(node, run.context)
            run.context.update(
                {"last_agent_output": agent_output, "last_node_id": node.id}
            )
            run.artifacts.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "output": dict(agent_output),
                }
            )
            run.messages.append(
                AgentMessage(
                    sender=str(run.context.get("last_sender", "workflow")),
                    receiver=node.agent_id or node.name,
                    timestamp=datetime.now(UTC),
                    payload=dict(agent_output),
                    reasoning=str(agent_output.get("reasoning", "")),
                    artifacts=[{"node_id": node.id, "output": dict(agent_output)}],
                    tool_outputs=list(agent_output.get("tool_outputs", [])),
                    metadata={"node_type": node.node_type, "node_name": node.name},
                )
            )
            run.context["last_sender"] = node.agent_id or node.name
            return [edge.target_node_id for edge in outgoing]

        if node.node_type == "Human Approval":
            auto_approve = bool(node.config.get("auto_approve", False))
            if auto_approve:
                return [edge.target_node_id for edge in outgoing]
            return []

        if node.node_type in {"Start", "Webhook", "REST", "Email", "Scheduler"}:
            return [edge.target_node_id for edge in outgoing]

        if node.node_type == "End":
            return []

        return [edge.target_node_id for edge in outgoing]

    @staticmethod
    def _compare(current: Any, expected: Any, operator: str) -> bool:
        if operator in {"eq", "equals", "=="}:
            return current == expected
        if operator in {"ne", "not_equals", "!="}:
            return current != expected
        if operator in {"contains"}:
            return str(expected) in str(current)
        if operator in {"gt", ">"}:
            try:
                return float(current) > float(expected)
            except (TypeError, ValueError):
                return False
        if operator in {"lt", "<"}:
            try:
                return float(current) < float(expected)
            except (TypeError, ValueError):
                return False
        return current == expected

    @staticmethod
    def _edge_map(edges: list[WorkflowEdge]) -> dict[str, list[WorkflowEdge]]:
        mapping: dict[str, list[WorkflowEdge]] = defaultdict(list)
        for edge in edges:
            mapping[edge.source_node_id].append(edge)
        return mapping

    @staticmethod
    def _incoming_map(edges: list[WorkflowEdge]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            mapping[edge.target_node_id].append(edge.source_node_id)
        return mapping

    def _ensure_record(
        self, run: WorkflowRun, node: WorkflowNode
    ) -> NodeExecutionRecord:
        with self._lock:
            existing = next(
                (item for item in run.node_records if item.node_id == node.id), None
            )
            if existing is not None:
                return existing
            record = NodeExecutionRecord(
                node_id=node.id,
                node_name=node.name,
                node_type=node.node_type,
            )
            run.node_records.append(record)
            return record

    @staticmethod
    def _log_event(
        event_type: str, message: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "message": message,
            "metadata": dict(metadata),
        }

    def _finalize_run(
        self,
        run: WorkflowRun,
        started: float,
        *,
        completed: bool = True,
    ) -> WorkflowRun:
        if completed and run.status in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELED,
        }:
            run.ended_at = datetime.now(UTC)
            run.duration_ms = round((perf_counter() - started) * 1000, 3)
            run.logs.append(
                self._log_event(
                    WORKFLOW_FINISHED,
                    "Workflow execution finished",
                    {
                        "run_id": run.id,
                        "status": run.status,
                        "duration_ms": run.duration_ms,
                    },
                )
            )
        run.touch()
        return run
