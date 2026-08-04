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
    WORKFLOW_NODE_WAITING,
    WORKFLOW_PAUSED,
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
        should_pause: Callable[[str], bool] | None = None,
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

            if should_pause is not None and should_pause(run.id):
                run.status = WorkflowRunStatus.PAUSED
                run.logs.append(
                    self._log_event(
                        WORKFLOW_PAUSED,
                        "Workflow execution paused",
                        {"run_id": run.id, "current_node_id": run.current_node_id},
                    )
                )
                run.touch()
                return self._finalize_run(run, started, completed=False)

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
                        "progress_percent": self._progress_percent(run),
                    },
                )
            )
            if node.node_type == "Human Approval":
                auto_approve = bool(node.config.get("auto_approve", False))
                if not auto_approve:
                    run.logs.append(
                        self._log_event(
                            WORKFLOW_NODE_WAITING,
                            f"Node waiting for approval: {node.name}",
                            {
                                "node_id": node.id,
                                "node_type": node.node_type,
                                "progress_percent": self._progress_percent(run),
                            },
                        )
                    )
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

        if node.node_type in {"Condition", "Decision"}:
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

        if node.node_type in {"Merge", "Parallel Join"}:
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
            runtime_context = run.context.setdefault("multi_agent_runtime", {})
            if isinstance(runtime_context, dict):
                if isinstance(agent_output.get("runtime_registry"), dict):
                    runtime_context["registry"] = dict(agent_output["runtime_registry"])
                if isinstance(agent_output.get("runtime_messages"), list):
                    runtime_context["messages"] = [
                        dict(item)
                        for item in agent_output.get("runtime_messages", [])
                        if isinstance(item, dict)
                    ]
                if isinstance(agent_output.get("runtime_timeline"), list):
                    runtime_context["timeline"] = [
                        dict(item)
                        for item in agent_output.get("runtime_timeline", [])
                        if isinstance(item, dict)
                    ]
                if isinstance(agent_output.get("runtime_artifacts"), list):
                    runtime_context["artifacts"] = [
                        dict(item)
                        for item in agent_output.get("runtime_artifacts", [])
                        if isinstance(item, dict)
                    ]
                if isinstance(agent_output.get("runtime_tasks"), list):
                    runtime_context["tasks"] = [
                        dict(item)
                        for item in agent_output.get("runtime_tasks", [])
                        if isinstance(item, dict)
                    ]
                if isinstance(agent_output.get("runtime_metrics"), dict):
                    runtime_context["metrics"] = dict(agent_output["runtime_metrics"])
                if isinstance(agent_output.get("runtime_supervisor"), dict):
                    runtime_context["supervisor"] = dict(
                        agent_output["runtime_supervisor"]
                    )
                if isinstance(agent_output.get("runtime_retries"), list):
                    runtime_context["retries"] = [
                        dict(item)
                        for item in agent_output.get("runtime_retries", [])
                        if isinstance(item, dict)
                    ]

            run.artifacts.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "output": dict(agent_output),
                }
            )
            runtime_messages = agent_output.get("runtime_messages", [])
            if isinstance(runtime_messages, list) and runtime_messages:
                for item in runtime_messages:
                    if not isinstance(item, dict):
                        continue
                    timestamp_raw = str(item.get("timestamp", ""))
                    try:
                        timestamp = datetime.fromisoformat(timestamp_raw)
                    except ValueError:
                        timestamp = datetime.now(UTC)
                    run.messages.append(
                        AgentMessage(
                            message_id=str(item.get("message_id", ""))
                            or str(datetime.now(UTC).timestamp()),
                            sender=str(item.get("sender_agent", ""))
                            or str(item.get("sender", "workflow")),
                            receiver=str(item.get("receiver_agent", ""))
                            or str(item.get("receiver", node.agent_id or node.name)),
                            sender_agent=str(item.get("sender_agent", "")),
                            receiver_agent=str(item.get("receiver_agent", "")),
                            task_id=str(item.get("task_id", "")),
                            priority=str(item.get("priority", "normal")),
                            message_type=str(item.get("message_type", "StatusUpdate")),
                            timestamp=timestamp,
                            conversation_id=str(
                                item.get(
                                    "conversation_id",
                                    run.context.get("conversation_id", ""),
                                )
                            ),
                            workflow_id=str(item.get("workflow_id", run.workflow_id)),
                            execution_id=str(item.get("execution_id", run.id)),
                            reasoning_summary=str(item.get("reasoning_summary", "")),
                            payload=dict(item.get("payload", {})),
                            confidence=float(item.get("confidence", 0.0) or 0.0),
                            attachments=[
                                dict(attachment)
                                for attachment in item.get("attachments", [])
                                if isinstance(attachment, dict)
                            ],
                            metadata={
                                "node_type": node.node_type,
                                "node_name": node.name,
                            },
                        )
                    )
            else:
                run.messages.append(
                    AgentMessage(
                        sender=str(run.context.get("last_sender", "workflow")),
                        receiver=node.agent_id or node.name,
                        sender_agent=str(run.context.get("last_sender", "workflow")),
                        receiver_agent=node.agent_id or node.name,
                        timestamp=datetime.now(UTC),
                        conversation_id=str(run.context.get("conversation_id", "")),
                        workflow_id=run.workflow_id,
                        execution_id=run.id,
                        thought=str(agent_output.get("thought", "")),
                        reasoning_summary=str(
                            agent_output.get("reasoning_summary", "")
                            or agent_output.get("reasoning", "")
                        ),
                        payload=dict(agent_output),
                        reasoning=str(agent_output.get("reasoning", "")),
                        artifacts=[{"node_id": node.id, "output": dict(agent_output)}],
                        tool_outputs=list(agent_output.get("tool_outputs", [])),
                        memory_references=list(
                            agent_output.get("memory_references", [])
                        ),
                        confidence=float(agent_output.get("confidence", 0.0) or 0.0),
                        metadata={"node_type": node.node_type, "node_name": node.name},
                    )
                )

            runtime_timeline = runtime_context.get("timeline", [])
            if isinstance(runtime_timeline, list):
                for item in runtime_timeline:
                    if not isinstance(item, dict):
                        continue
                    run.logs.append(
                        self._log_event(
                            "WORKFLOW_AGENT_TIMELINE",
                            str(item.get("action", "agent-action")),
                            {
                                "agent": str(item.get("agent", "")),
                                "node_id": node.id,
                                "duration_ms": float(
                                    item.get("duration_ms", 0.0) or 0.0
                                ),
                                "details": dict(item),
                            },
                        )
                    )

            runtime_artifacts = runtime_context.get("artifacts", [])
            if isinstance(runtime_artifacts, list):
                for artifact in runtime_artifacts:
                    if isinstance(artifact, dict):
                        run.artifacts.append(dict(artifact))

            run.context["last_sender"] = node.agent_id or node.name
            return [edge.target_node_id for edge in outgoing]

        if node.node_type == "Delay":
            delay_ms = int(node.config.get("delay_ms", 0) or 0)
            run.context["last_delay_ms"] = delay_ms
            return [edge.target_node_id for edge in outgoing]

        if node.node_type in {
            "Memory",
            "Knowledge Search",
            "Python Tool",
            "REST Tool",
            "Filesystem Tool",
        }:
            integration_payload = {
                "node_id": node.id,
                "node_type": node.node_type,
                "config": dict(node.config),
                "status": "completed",
            }
            run.context[f"{node.id}_result"] = integration_payload
            run.artifacts.append(integration_payload)
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

    @staticmethod
    def _progress_percent(run: WorkflowRun) -> float:
        if not run.node_records:
            return 0.0
        completed = sum(
            1 for record in run.node_records if record.status == "completed"
        )
        total = len(run.node_records)
        return round((completed / max(1, total)) * 100.0, 2)
