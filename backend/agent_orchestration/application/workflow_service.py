"""Application service for workflow orchestration operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.agent_orchestration.domain.run import WorkflowRun, WorkflowRunStatus
from backend.agent_orchestration.domain.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)
from backend.agent_orchestration.events import WORKFLOW_CREATED, WORKFLOW_UPDATED
from backend.agent_orchestration.executor.workflow_executor import (
    WorkflowExecutionEngine,
)
from backend.agent_orchestration.models.workflow import (
    AutonomousMissionRequest,
    MissionTemplateRequest,
    WorkflowCreateRequest,
    WorkflowExecutionRequest,
    WorkflowRunActionRequest,
    WorkflowUpdateRequest,
)
from backend.agent_orchestration.planner.validator import WorkflowValidator
from backend.agent_orchestration.repository.workflow_repository import (
    WorkflowRepository,
)
from backend.agent_orchestration.runtime import (
    AutonomousPlanner,
    CapabilityScoringEngine,
    MultiAgentRuntime,
)
from backend.agent_orchestration.runtime.autonomous_planner import PlannerContext
from backend.agent_orchestration.scheduler.background_scheduler import (
    BackgroundWorkflowScheduler,
)
from backend.agent_studio.application.agent_service import AgentService
from backend.core.logging.logger import LoggerFactory
from backend.llm.client import OllamaClient

logger = LoggerFactory.get_logger("WorkflowService")


class WorkflowService:
    """Coordinates workflow persistence, validation, and execution."""

    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        validator: WorkflowValidator,
        engine: WorkflowExecutionEngine,
        scheduler: BackgroundWorkflowScheduler,
        agent_service: AgentService,
        llm_client: OllamaClient,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._engine = engine
        self._scheduler = scheduler
        self._agent_service = agent_service
        self._llm_client = llm_client
        self._multi_agent_runtime = MultiAgentRuntime()
        self._autonomous_planner = AutonomousPlanner()
        self._capability_engine = CapabilityScoringEngine()

    def list_workflows(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Workflow]:
        """List workflows in ownership scope."""
        return self._repository.list_workflows(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def get_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Workflow | None:
        """Return one workflow by identifier."""
        return self._repository.get_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def create_workflow(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: WorkflowCreateRequest,
    ) -> Workflow:
        """Create and persist a new workflow."""
        workflow = Workflow.create(
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            nodes=self._build_nodes(payload.nodes),
            edges=self._build_edges(payload.edges),
            execution_settings=dict(payload.execution_settings),
            shared_memory_settings=dict(payload.shared_memory_settings),
            approval_settings=dict(payload.approval_settings),
            retry_settings=dict(payload.retry_settings),
            timeout_settings=dict(payload.timeout_settings),
        )
        validation = self.validate_workflow_definition(
            workflow,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if not bool(validation.get("valid", False)):
            errors = list(validation.get("errors", []))
            raise ValueError("Workflow validation failed: " + "; ".join(errors))

        created = self._repository.create_workflow(workflow)
        self._repository.create_workflow_version(
            created.id,
            version_number=created.version,
            change_summary="Created workflow",
            snapshot=created.to_snapshot(),
        )
        logger.info(
            "%s workflow_id=%s owner_id=%s workspace_id=%s project_id=%s",
            WORKFLOW_CREATED,
            created.id,
            owner_id,
            workspace_id,
            project_id,
        )
        return created

    def update_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: WorkflowUpdateRequest,
    ) -> Workflow:
        """Apply partial updates and persist workflow version."""
        current = self._require_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

        if payload.name is not None:
            current.name = payload.name
        if payload.description is not None:
            current.description = payload.description
        if payload.enabled is not None:
            current.enabled = payload.enabled
        if payload.nodes is not None:
            current.nodes = self._build_nodes(payload.nodes)
        if payload.edges is not None:
            current.edges = self._build_edges(payload.edges)
        if payload.execution_settings is not None:
            current.execution_settings = dict(payload.execution_settings)
        if payload.shared_memory_settings is not None:
            current.shared_memory_settings = dict(payload.shared_memory_settings)
        if payload.approval_settings is not None:
            current.approval_settings = dict(payload.approval_settings)
        if payload.retry_settings is not None:
            current.retry_settings = dict(payload.retry_settings)
        if payload.timeout_settings is not None:
            current.timeout_settings = dict(payload.timeout_settings)

        validation = self.validate_workflow_definition(
            current,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if not bool(validation.get("valid", False)):
            errors = list(validation.get("errors", []))
            raise ValueError("Workflow validation failed: " + "; ".join(errors))

        current.version += 1
        current.touch()
        updated = self._repository.update_workflow(current)
        self._repository.create_workflow_version(
            updated.id,
            version_number=updated.version,
            change_summary="Updated workflow",
            snapshot=updated.to_snapshot(),
        )
        logger.info(
            "%s workflow_id=%s version=%s",
            WORKFLOW_UPDATED,
            updated.id,
            updated.version,
        )
        return updated

    def delete_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        """Delete a workflow in ownership scope."""
        return self._repository.delete_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def list_workflow_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        """List version history for one workflow."""
        return self._repository.list_workflow_versions(workflow_id)

    def validate_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Validate one persisted workflow."""
        workflow = self._require_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        return self.validate_workflow_definition(
            workflow,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def validate_workflow_definition(
        self,
        workflow: Workflow,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Validate a workflow aggregate against graph and agent references."""
        agents = self._agent_service.list_agents(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        known_ids = {agent.id for agent in agents}
        return self._validator.validate(workflow, known_agent_ids=known_ids)

    def execute_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: WorkflowExecutionRequest,
    ) -> WorkflowRun:
        """Create a workflow run and execute either sync or async."""
        workflow = self._require_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if not workflow.enabled:
            raise ValueError("Workflow is disabled")

        run = WorkflowRun(
            workflow_id=workflow.id,
            input_payload=dict(payload.input_payload),
            context={
                **dict(payload.input_payload),
                "conversation_id": payload.conversation_id,
                "workflow_id": workflow.id,
                "owner_id": owner_id,
                "workspace_id": workspace_id,
                "project_id": project_id,
                "workflow_memory": {},
                "conversation_memory": {},
                "project_memory": {},
                "shared_variables": dict(payload.shared_variables),
                "artifacts": [],
                "temporary_files": [],
                "execution_metadata": {
                    "requested_at": datetime.now(UTC).isoformat(),
                    "workflow_id": workflow.id,
                },
                "multi_agent_runtime": {
                    "registry": {},
                    "messages": [],
                    "timeline": [],
                    "artifacts": [],
                    "tasks": [],
                    "metrics": {},
                    "supervisor": {},
                    "retries": [],
                },
            },
            status=WorkflowRunStatus.QUEUED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        run.context["execution_id"] = run.id
        self._repository.create_run(run)

        if payload.wait_for_completion:
            completed = self._execute_run(workflow=workflow, run_id=run.id)
            return completed

        self._scheduler.submit(
            run.id,
            lambda: self._execute_run(workflow=workflow, run_id=run.id),
        )
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Fetch one run by identifier."""
        return self._repository.get_run(run_id)

    def list_runs(self, workflow_id: str) -> list[WorkflowRun]:
        """List all runs for a workflow."""
        return self._repository.list_runs(workflow_id)

    def list_recent_runs(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        limit: int,
    ) -> list[WorkflowRun]:
        """List recent scoped runs."""
        return self._repository.list_recent_runs(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            limit=limit,
        )

    def cancel_run(self, run_id: str) -> WorkflowRun:
        """Mark a run for cancellation."""
        run = self._require_run(run_id)
        run.cancel_requested = True
        if run.status == WorkflowRunStatus.QUEUED:
            run.status = WorkflowRunStatus.CANCELED
            run.error = "Execution canceled before start"
            run.ended_at = datetime.now(UTC)
        run.touch()
        return self._repository.update_run(run)

    def pause_run(self, run_id: str) -> WorkflowRun:
        """Pause a queued or running execution."""
        run = self._require_run(run_id)
        if run.status not in {WorkflowRunStatus.QUEUED, WorkflowRunStatus.RUNNING}:
            raise ValueError("Run cannot be paused from current state")
        run.status = WorkflowRunStatus.PAUSED
        if run.current_node_id:
            run.context["resume_from_nodes"] = [run.current_node_id]
        run.touch()
        return self._repository.update_run(run)

    def resume_run(self, run_id: str) -> WorkflowRun:
        """Resume a paused execution."""
        run = self._require_run(run_id)
        if run.status != WorkflowRunStatus.PAUSED:
            raise ValueError("Run is not paused")

        workflow = self._repository.get_workflow(
            run.workflow_id,
            owner_id=str(run.context.get("owner_id", "anonymous")),
            workspace_id=str(run.context.get("workspace_id", "default")),
            project_id=str(run.context.get("project_id", "default")),
        )
        if workflow is None:
            raise ValueError("Workflow not found for run")

        run.status = WorkflowRunStatus.RUNNING
        run.touch()
        self._repository.update_run(run)
        self._scheduler.submit(
            run.id,
            lambda: self._execute_run(workflow=workflow, run_id=run.id),
        )
        return run

    def apply_run_action(
        self, run_id: str, payload: WorkflowRunActionRequest
    ) -> WorkflowRun:
        """Handle human approval actions for paused runs."""
        run = self._require_run(run_id)
        if run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("Run is not waiting for approval")

        workflow = self._repository.get_workflow(
            run.workflow_id,
            owner_id=str(run.context.get("owner_id", "anonymous")),
            workspace_id=str(run.context.get("workspace_id", "default")),
            project_id=str(run.context.get("project_id", "default")),
        )
        if workflow is None:
            raise ValueError("Workflow not found for run")

        action = payload.action.strip().lower()
        if action in {"reject", "cancel"}:
            run.status = WorkflowRunStatus.CANCELED
            run.error = "Execution canceled by user"
            run.pending_node_id = ""
            run.ended_at = datetime.now(UTC)
            run.touch()
            return self._repository.update_run(run)

        if action not in {"approve", "edit"}:
            raise ValueError("Unsupported run action")

        pending_node_id = run.pending_node_id
        if action == "edit":
            run.context["edited_input"] = dict(payload.edited_input)

        next_nodes = self._next_nodes_after_pending(workflow, pending_node_id)
        run.pending_node_id = ""
        run.status = WorkflowRunStatus.RUNNING
        run.context["resume_from_nodes"] = list(next_nodes)
        run.touch()
        self._repository.update_run(run)

        self._scheduler.submit(
            run.id,
            lambda: self._execute_run(workflow=workflow, run_id=run.id),
        )
        return run

    def get_dashboard(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Return orchestration dashboard metrics."""
        return self._repository.dashboard_metrics(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def compare_versions(
        self,
        workflow_id: str,
        *,
        left_version: int,
        right_version: int,
    ) -> dict[str, Any]:
        """Compare two workflow versions and return changed fields."""
        versions = self._repository.list_workflow_versions(workflow_id)
        indexed = {int(item["version_number"]): item for item in versions}
        left = indexed.get(left_version)
        right = indexed.get(right_version)
        if left is None or right is None:
            raise KeyError("Version not found")

        left_snapshot = dict(left.get("snapshot", {}))
        right_snapshot = dict(right.get("snapshot", {}))
        fields = sorted(set(left_snapshot.keys()) | set(right_snapshot.keys()))
        differences: list[dict[str, Any]] = []
        for field_name in fields:
            before = left_snapshot.get(field_name)
            after = right_snapshot.get(field_name)
            if before != after:
                differences.append(
                    {
                        "field": field_name,
                        "before": before,
                        "after": after,
                    }
                )

        return {
            "workflow_id": workflow_id,
            "left_version": left_version,
            "right_version": right_version,
            "differences": differences,
        }

    def restore_version(
        self,
        workflow_id: str,
        *,
        version_id: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Workflow:
        """Restore a version snapshot and persist as a new version."""
        current = self._require_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        versions = self._repository.list_workflow_versions(workflow_id)
        version = next(
            (item for item in versions if str(item.get("id")) == version_id), None
        )
        if version is None:
            raise KeyError("Version not found")

        restored = Workflow.from_snapshot(dict(version.get("snapshot", {})))
        restored.id = current.id
        restored.owner_id = owner_id
        restored.workspace_id = workspace_id
        restored.project_id = project_id
        restored.version = current.version + 1
        restored.created_at = current.created_at
        restored.touch()

        updated = self._repository.update_workflow(restored)
        self._repository.create_workflow_version(
            updated.id,
            version_number=updated.version,
            change_summary=f"Restored version {version_id}",
            snapshot=updated.to_snapshot(),
        )
        return updated

    def get_run_debugger(self, run_id: str) -> dict[str, Any]:
        """Return debugger payload for deep node-by-node inspection."""
        run = self._require_run(run_id)
        workflow = self._repository.get_workflow(
            run.workflow_id,
            owner_id=str(run.context.get("owner_id", "anonymous")),
            workspace_id=str(run.context.get("workspace_id", "default")),
            project_id=str(run.context.get("project_id", "default")),
        )
        node_map: dict[str, dict[str, Any]] = {}
        if workflow is not None:
            node_map = {
                node.id: {
                    "id": node.id,
                    "name": node.name,
                    "node_type": node.node_type,
                    "agent_id": node.agent_id,
                    "config": dict(node.config),
                }
                for node in workflow.nodes
            }

        return {
            "run": run,
            "workflow": workflow,
            "nodes": node_map,
            "timeline": list(run.logs),
            "runtime": dict(run.context.get("multi_agent_runtime", {})),
            "messages": [
                {
                    "message_id": message.message_id,
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "sender_agent": message.sender_agent,
                    "receiver_agent": message.receiver_agent,
                    "task_id": message.task_id,
                    "priority": message.priority,
                    "message_type": message.message_type,
                    "timestamp": message.timestamp.isoformat(),
                    "thought": message.thought,
                    "reasoning_summary": message.reasoning_summary,
                    "payload": dict(message.payload),
                    "tool_outputs": list(message.tool_outputs),
                    "memory_references": list(message.memory_references),
                    "attachments": list(message.attachments),
                    "confidence": message.confidence,
                }
                for message in run.messages
            ],
        }

    def get_agent_registry(self, run_id: str) -> dict[str, Any]:
        """Return agent registry snapshots for one run."""
        run = self._require_run(run_id)
        runtime = dict(run.context.get("multi_agent_runtime", {}))
        return dict(runtime.get("registry", {}))

    def get_agent_messages(self, run_id: str) -> list[dict[str, Any]]:
        """Return structured runtime messages for one run."""
        run = self._require_run(run_id)
        runtime = dict(run.context.get("multi_agent_runtime", {}))
        runtime_messages = runtime.get("messages", [])
        if isinstance(runtime_messages, list) and runtime_messages:
            return [dict(item) for item in runtime_messages if isinstance(item, dict)]

        return [
            {
                "message_id": message.message_id,
                "workflow_id": message.workflow_id,
                "execution_id": message.execution_id,
                "conversation_id": message.conversation_id,
                "sender_agent": message.sender_agent or message.sender,
                "receiver_agent": message.receiver_agent or message.receiver,
                "task_id": message.task_id,
                "timestamp": message.timestamp.isoformat(),
                "priority": message.priority,
                "message_type": message.message_type,
                "payload": dict(message.payload),
                "reasoning_summary": message.reasoning_summary,
                "confidence": message.confidence,
                "attachments": list(message.attachments),
            }
            for message in run.messages
        ]

    def get_execution_timeline(self, run_id: str) -> list[dict[str, Any]]:
        """Return agent runtime timeline for one run."""
        run = self._require_run(run_id)
        runtime = dict(run.context.get("multi_agent_runtime", {}))
        timeline = runtime.get("timeline", [])
        if isinstance(timeline, list) and timeline:
            return [dict(item) for item in timeline if isinstance(item, dict)]

        return [dict(item) for item in run.logs if isinstance(item, dict)]

    def get_execution_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """Return runtime and workflow artifacts for one run."""
        run = self._require_run(run_id)
        runtime = dict(run.context.get("multi_agent_runtime", {}))
        runtime_artifacts = runtime.get("artifacts", [])
        if isinstance(runtime_artifacts, list) and runtime_artifacts:
            return [dict(item) for item in runtime_artifacts if isinstance(item, dict)]
        return [dict(item) for item in run.artifacts if isinstance(item, dict)]

    def get_supervisor_state(self, run_id: str) -> dict[str, Any]:
        """Return supervisor state and retry policy for one run."""
        run = self._require_run(run_id)
        runtime = dict(run.context.get("multi_agent_runtime", {}))
        supervisor = runtime.get("supervisor", {})
        if isinstance(supervisor, dict) and supervisor:
            return dict(supervisor)
        return {
            "agent_id": "",
            "state": run.status,
            "total_tasks": len(run.node_records),
            "completed_tasks": len(
                [record for record in run.node_records if record.status == "completed"]
            ),
            "failed_tasks": len(
                [record for record in run.node_records if record.status == "failed"]
            ),
            "retry_policy": "immediate",
        }

    def retry_run(
        self,
        run_id: str,
        *,
        policy: str,
        task_id: str,
    ) -> WorkflowRun:
        """Retry a failed/canceled run under supervisor-selected policy."""
        run = self._require_run(run_id)
        if run.status not in {WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELED}:
            raise ValueError("Run can only be retried from failed or canceled state")

        workflow = self._repository.get_workflow(
            run.workflow_id,
            owner_id=str(run.context.get("owner_id", "anonymous")),
            workspace_id=str(run.context.get("workspace_id", "default")),
            project_id=str(run.context.get("project_id", "default")),
        )
        if workflow is None:
            raise ValueError("Workflow not found for retry")

        run.cancel_requested = False
        run.error = ""
        run.status = WorkflowRunStatus.QUEUED
        run.ended_at = None
        run.context["runtime_retry_request"] = {
            "policy": policy,
            "task_id": task_id,
            "requested_at": datetime.now(UTC).isoformat(),
        }
        if run.current_node_id:
            run.context["resume_from_nodes"] = [run.current_node_id]
        run.touch()
        self._repository.update_run(run)
        self._scheduler.submit(
            run.id,
            lambda: self._execute_run(workflow=workflow, run_id=run.id),
        )
        return run

    def create_autonomous_mission(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AutonomousMissionRequest,
    ) -> dict[str, Any]:
        """Plan and optionally execute one autonomous mission."""
        workflows = self._repository.list_workflows(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        agents = self._agent_service.list_agents(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        recent_runs = self._repository.list_recent_runs(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            limit=200,
        )

        workload: dict[str, int] = {}
        success: dict[str, float] = {}
        for run in recent_runs:
            for message in run.messages:
                agent_id = message.receiver_agent or message.receiver
                if not agent_id:
                    continue
                workload[agent_id] = workload.get(agent_id, 0) + int(
                    run.status in {WorkflowRunStatus.RUNNING, WorkflowRunStatus.QUEUED}
                )
                entry = success.setdefault(agent_id, 0.5)
                if run.status == WorkflowRunStatus.SUCCEEDED:
                    success[agent_id] = min(1.0, entry + 0.02)
                elif run.status == WorkflowRunStatus.FAILED:
                    success[agent_id] = max(0.0, entry - 0.03)

        workflow_snapshots = [
            {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "nodes": [
                    {"id": node.id, "name": node.name, "node_type": node.node_type}
                    for node in workflow.nodes
                ],
            }
            for workflow in workflows
        ]
        agent_snapshots = [
            {
                "id": agent.id,
                "name": agent.name,
                "capabilities": list(getattr(agent, "capabilities", [])),
                "tags": list(getattr(agent, "tags", [])),
                "tools_allowed": list(getattr(agent, "tools_allowed", [])),
                "knowledge_sources": (
                    list(getattr(agent, "knowledge_source_ids", []))
                    + list(getattr(agent, "github_repositories", []))
                    + list(getattr(agent, "sharepoint_sites", []))
                ),
            }
            for agent in agents
        ]

        plan = self._autonomous_planner.plan(
            context=self._autonomous_planner_context(
                goal=payload.goal,
                constraints=list(payload.constraints),
                context=dict(payload.context),
                workflows=workflow_snapshots,
                agents=agent_snapshots,
                agent_workload=workload,
                agent_success=success,
            )
        )

        mission_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        mission: dict[str, Any] = {
            "mission_id": mission_id,
            "goal": payload.goal,
            "status": "planned",
            "owner_id": owner_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "run_id": "",
            "selected_workflow_id": str(
                plan.get("workflow_reuse", {}).get("selected_workflow_id", "")
            ),
            "planner_output": dict(plan),
            "capability_scores": list(plan.get("capability_scores", [])),
            "execution_recommendations": list(plan.get("recommendations", [])),
            "temporary_agents": list(plan.get("temporary_agents", [])),
            "mission_timeline": [
                {
                    "timestamp": now,
                    "event": "mission_planned",
                    "detail": "Autonomous planner generated task graph and selection rationale.",
                }
            ],
            "artifacts": [],
            "governance": {
                "requires_approval": bool(plan.get("requires_approval", False)),
                "required_approvals": list(plan.get("required_approvals", [])),
            },
            "execution_result": {},
            "created_at": now,
            "updated_at": now,
        }
        self._repository.create_mission(mission)

        if not payload.auto_execute:
            return mission

        mission["status"] = "running"
        mission["updated_at"] = datetime.now(UTC).isoformat()
        mission["mission_timeline"].append(
            {
                "timestamp": mission["updated_at"],
                "event": "execution_started",
                "detail": "Mission execution started by autonomous supervisor.",
            }
        )
        self._repository.update_mission(mission)

        workflow_reuse = dict(plan.get("workflow_reuse", {}))
        reuse = bool(workflow_reuse.get("reuse", False))
        selected_workflow_id = str(workflow_reuse.get("selected_workflow_id", ""))

        if reuse and selected_workflow_id:
            run = self.execute_workflow(
                selected_workflow_id,
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
                payload=WorkflowExecutionRequest(
                    input_payload={
                        "mission_id": mission_id,
                        "goal": payload.goal,
                        "planner_output": dict(plan),
                    },
                    conversation_id="",
                    shared_variables=dict(payload.context),
                    wait_for_completion=payload.wait_for_completion,
                ),
            )
            mission["run_id"] = run.id
            mission["status"] = (
                "running"
                if run.status in {WorkflowRunStatus.QUEUED, WorkflowRunStatus.RUNNING}
                else str(run.status)
            )
            mission["updated_at"] = datetime.now(UTC).isoformat()
            mission["mission_timeline"].append(
                {
                    "timestamp": mission["updated_at"],
                    "event": "workflow_reused",
                    "detail": f"Reused workflow {selected_workflow_id} for mission execution.",
                }
            )
            self._repository.update_mission(mission)
            return mission

        runtime_result = self._execute_autonomous_runtime(
            goal=payload.goal,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            plan=plan,
            mission_id=mission_id,
        )
        mission["execution_result"] = dict(runtime_result)
        mission["artifacts"] = list(runtime_result.get("artifacts", []))
        mission["mission_timeline"].extend(
            list(runtime_result.get("timeline", []))[:60]
        )
        mission["status"] = (
            "completed" if runtime_result.get("status") == "completed" else "failed"
        )

        if mission["status"] == "failed":
            replanned = self._replan_after_failure(payload.goal, plan)
            mission["planner_output"]["replanned"] = replanned
            mission["execution_recommendations"].append(
                {
                    "type": "replan",
                    "message": "Mission failed during autonomous runtime; replanned graph is attached.",
                }
            )

        mission["updated_at"] = datetime.now(UTC).isoformat()
        mission["mission_timeline"].append(
            {
                "timestamp": mission["updated_at"],
                "event": "execution_finished",
                "detail": "Mission execution finished in autonomous runtime.",
            }
        )
        self._repository.update_mission(mission)
        return mission

    def list_autonomous_missions(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """List recent autonomous missions in ownership scope."""
        return self._repository.list_missions(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            limit=limit,
        )

    def get_autonomous_mission(self, mission_id: str) -> dict[str, Any]:
        """Fetch one mission by identifier."""
        mission = self._repository.get_mission(mission_id)
        if mission is None:
            raise KeyError(f"Mission not found: {mission_id}")
        return mission

    def get_autonomous_mission_status(self, mission_id: str) -> dict[str, Any]:
        """Return concise mission status for polling."""
        mission = self.get_autonomous_mission(mission_id)
        return {
            "mission_id": mission_id,
            "status": str(mission.get("status", "planned")),
            "run_id": str(mission.get("run_id", "")),
            "selected_workflow_id": str(mission.get("selected_workflow_id", "")),
            "updated_at": datetime.fromisoformat(str(mission.get("updated_at"))),
        }

    def get_autonomous_mission_planner_output(self, mission_id: str) -> dict[str, Any]:
        """Return planner output for mission explainability."""
        mission = self.get_autonomous_mission(mission_id)
        return dict(mission.get("planner_output", {}))

    def get_autonomous_mission_capability_scores(
        self, mission_id: str
    ) -> list[dict[str, Any]]:
        """Return mission capability scoring details."""
        mission = self.get_autonomous_mission(mission_id)
        return [
            dict(item)
            for item in mission.get("capability_scores", [])
            if isinstance(item, dict)
        ]

    def get_autonomous_mission_recommendations(
        self, mission_id: str
    ) -> list[dict[str, Any]]:
        """Return planner recommendations for one mission."""
        mission = self.get_autonomous_mission(mission_id)
        return [
            dict(item)
            for item in mission.get("execution_recommendations", [])
            if isinstance(item, dict)
        ]

    def get_autonomous_mission_temporary_agents(
        self, mission_id: str
    ) -> list[dict[str, Any]]:
        """Return mission temporary execution-agent descriptors."""
        mission = self.get_autonomous_mission(mission_id)
        return [
            dict(item)
            for item in mission.get("temporary_agents", [])
            if isinstance(item, dict)
        ]

    def mission_control_dashboard(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Aggregate mission-control metrics for current ownership scope."""
        missions = self._repository.list_missions(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            limit=500,
        )
        completed = [m for m in missions if str(m.get("status", "")) == "completed"]
        failed = [m for m in missions if str(m.get("status", "")) == "failed"]
        running = [m for m in missions if str(m.get("status", "")) == "running"]
        planned = [m for m in missions if str(m.get("status", "")) == "planned"]

        runtimes: list[float] = []
        retries = 0
        for mission in missions:
            planner_output = mission.get("planner_output", {})
            if isinstance(planner_output, dict):
                runtimes.append(
                    float(planner_output.get("estimated_runtime_ms", 0.0) or 0.0)
                )
            execution = mission.get("execution_result", {})
            if isinstance(execution, dict):
                metrics = execution.get("metrics", {})
                if isinstance(metrics, dict):
                    retries += int(metrics.get("retries", 0) or 0)

        return {
            "running_missions": len(running),
            "planned_missions": len(planned),
            "completed_missions": len(completed),
            "failed_missions": len(failed),
            "mission_success_rate": (
                len(completed) / max(1, (len(completed) + len(failed)))
            ),
            "average_runtime_ms": sum(runtimes) / max(1, len(runtimes)),
            "active_runs": len([m for m in missions if str(m.get("run_id", ""))]),
            "retries": retries,
            "recent_failures": [
                {
                    "mission_id": str(item.get("mission_id", "")),
                    "goal": str(item.get("goal", "")),
                    "updated_at": str(item.get("updated_at", "")),
                }
                for item in failed[:10]
            ],
        }

    def create_mission_template(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: MissionTemplateRequest,
    ) -> dict[str, Any]:
        """Create a reusable mission execution template."""
        now = datetime.now(UTC).isoformat()
        template = {
            "template_id": str(uuid4()),
            "owner_id": owner_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "name": payload.name,
            "description": payload.description,
            "template": dict(payload.template),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        return self._repository.create_mission_template(template)

    def update_mission_template(
        self,
        template_id: str,
        *,
        payload: MissionTemplateRequest,
    ) -> dict[str, Any]:
        """Update an existing mission template and increment version."""
        current = self._repository.get_mission_template(template_id)
        if current is None:
            raise KeyError("Mission template not found")
        current["name"] = payload.name
        current["description"] = payload.description
        current["template"] = dict(payload.template)
        current["version"] = int(current.get("version", 1)) + 1
        current["updated_at"] = datetime.now(UTC).isoformat()
        return self._repository.update_mission_template(current)

    def list_mission_templates(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """List available mission templates for current scope."""
        return self._repository.list_mission_templates(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def _execute_run(self, *, workflow: Workflow, run_id: str) -> WorkflowRun:
        run = self._require_run(run_id)
        resume_from_nodes: list[str] = []
        if isinstance(run.context.get("resume_from_nodes"), list):
            resume_from_nodes = [
                str(item)
                for item in run.context.get("resume_from_nodes", [])
                if isinstance(item, str)
            ]
        if "resume_from_nodes" in run.context:
            run.context.pop("resume_from_nodes", None)

        executed = self._engine.execute(
            workflow=workflow,
            run=run,
            agent_evaluator=self._evaluate_agent_node,
            should_cancel=self._should_cancel,
            should_pause=self._should_pause,
            start_node_ids=resume_from_nodes or None,
        )
        return self._repository.update_run(executed)

    def _evaluate_agent_node(
        self,
        node: WorkflowNode,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if not node.agent_id:
            raise ValueError(f"Agent node {node.id} is missing agent id")

        owner_id = str(context.get("owner_id", "anonymous"))
        workspace_id = str(context.get("workspace_id", "default"))
        project_id = str(context.get("project_id", "default"))

        agent = self._agent_service.get_agent(
            node.agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if agent is None:
            raise ValueError(f"Agent not found: {node.agent_id}")

        runtime_config = {
            "planner_agent_id": str(
                node.config.get("planner_agent_id", "planner-agent")
            ),
            "supervisor_agent_id": str(
                node.config.get("supervisor_agent_id", "supervisor-agent")
            ),
            "max_retries": int(node.config.get("max_retries", 1) or 1),
            "retry_policy": str(node.config.get("retry_policy", "immediate")),
            "planned_tasks": (
                list(node.config.get("planned_tasks", []))
                if isinstance(node.config.get("planned_tasks", []), list)
                else []
            ),
            "shared_variables": dict(context.get("shared_variables", {})),
        }

        available_agents = self._agent_service.list_agents(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

        available_agent_descriptors = [
            {
                "id": item.id,
                "capabilities": list(
                    getattr(item, "capabilities", ["general"])
                    if isinstance(getattr(item, "capabilities", ["general"]), list)
                    else ["general"]
                ),
                "tags": (
                    list(getattr(item, "tags", []))
                    if isinstance(getattr(item, "tags", []), list)
                    else []
                ),
                "allowed_tools": (
                    list(getattr(item, "allowed_tools", []))
                    if isinstance(getattr(item, "allowed_tools", []), list)
                    else []
                ),
                "knowledge_sources": (
                    list(getattr(item, "knowledge_sources", []))
                    if isinstance(getattr(item, "knowledge_sources", []), list)
                    else []
                ),
            }
            for item in available_agents
        ]

        def _execute_agent(
            agent_id: str,
            task_prompt: str,
            task_context: dict[str, Any],
        ) -> dict[str, Any]:
            runtime_agent = self._agent_service.get_agent(
                agent_id,
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            if runtime_agent is None:
                raise ValueError(f"Delegated agent not found: {agent_id}")

            payload = {
                "node": {
                    "id": node.id,
                    "name": node.name,
                    "config": dict(node.config),
                },
                "task": {
                    "prompt": task_prompt,
                    "context": task_context,
                },
                "context": dict(context),
            }
            prompt = (
                f"Agent task: {task_prompt}\n"
                f"Agent goal: {runtime_agent.goal}\n"
                f"Agent instructions: {runtime_agent.instructions}\n"
                "Return JSON with keys: result, reasoning, tool_outputs, "
                "memory_references, knowledge_references, confidence.\n"
                f"Payload: {json.dumps(payload, ensure_ascii=True)}"
            )
            response = self._llm_client.generate(
                prompt=prompt,
                system=runtime_agent.system_prompt,
                model=runtime_agent.model or None,
                temperature=runtime_agent.temperature,
                format_json=True,
            )
            if isinstance(response, dict):
                output = dict(response)
            else:
                output = {
                    "result": str(response),
                    "reasoning": "",
                    "tool_outputs": [],
                    "memory_references": [],
                    "knowledge_references": [],
                    "confidence": 0.6,
                }
            output.setdefault("result", "")
            output.setdefault("reasoning", "")
            output.setdefault("tool_outputs", [])
            output.setdefault("memory_references", [])
            output.setdefault("knowledge_references", [])
            output.setdefault("confidence", 0.6)
            output["agent_id"] = runtime_agent.id
            output["agent_name"] = runtime_agent.name
            return output

        runtime_output = self._multi_agent_runtime.run_goal(
            workflow_id=str(context.get("workflow_id", "")),
            execution_id=str(context.get("execution_id", "")),
            conversation_id=str(context.get("conversation_id", "")),
            node_id=node.id,
            node_name=node.name,
            goal=node.name,
            runtime_context=runtime_config,
            available_agents=available_agent_descriptors,
            execute_agent=_execute_agent,
        )

        if runtime_output.get("status") == "failed" and not bool(
            node.config.get("allow_partial", False)
        ):
            raise ValueError("Multi-agent runtime failed to complete delegated tasks")

        output = {
            "result": str(runtime_output.get("result", "")),
            "reasoning": str(runtime_output.get("reasoning", "")),
            "tool_outputs": [],
            "memory_references": [],
            "confidence": float(runtime_output.get("confidence", 0.7) or 0.7),
            "agent_id": node.agent_id,
            "agent_name": agent.name,
            "runtime_registry": dict(runtime_output.get("registry", {})),
            "runtime_messages": list(runtime_output.get("messages", [])),
            "runtime_timeline": list(runtime_output.get("timeline", [])),
            "runtime_artifacts": list(runtime_output.get("artifacts", [])),
            "runtime_tasks": list(runtime_output.get("tasks", [])),
            "runtime_metrics": dict(runtime_output.get("metrics", {})),
            "runtime_supervisor": dict(runtime_output.get("supervisor", {})),
            "runtime_retries": list(runtime_output.get("retries", [])),
        }
        return output

    def _should_cancel(self, run_id: str) -> bool:
        latest = self._repository.get_run(run_id)
        if latest is None:
            return True
        return latest.cancel_requested

    def _should_pause(self, run_id: str) -> bool:
        latest = self._repository.get_run(run_id)
        if latest is None:
            return False
        return latest.status == WorkflowRunStatus.PAUSED

    def _autonomous_planner_context(
        self,
        *,
        goal: str,
        constraints: list[str],
        context: dict[str, Any],
        workflows: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        agent_workload: dict[str, int],
        agent_success: dict[str, float],
    ) -> PlannerContext:
        return PlannerContext(
            goal=goal,
            constraints=constraints,
            context=context,
            workflows=workflows,
            agents=agents,
            agent_workload=agent_workload,
            agent_success=agent_success,
        )

    def _execute_autonomous_runtime(
        self,
        *,
        goal: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        plan: dict[str, Any],
        mission_id: str,
    ) -> dict[str, Any]:
        task_graph = [
            dict(item) for item in plan.get("task_graph", []) if isinstance(item, dict)
        ]
        planned_tasks = [
            {
                "task_id": str(item.get("task_id", "")),
                "title": str(item.get("title", "Task")),
                "description": str(item.get("description", "")),
                "required_capabilities": self._capability_engine.infer_required_capabilities(
                    str(item.get("description", ""))
                ),
            }
            for item in task_graph
        ]

        runtime_agents = self._agent_service.list_agents(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        available_agent_descriptors = [
            {
                "id": item.id,
                "capabilities": list(
                    getattr(item, "capabilities", ["general"])
                    if isinstance(getattr(item, "capabilities", ["general"]), list)
                    else ["general"]
                ),
                "tags": (
                    list(getattr(item, "tags", []))
                    if isinstance(getattr(item, "tags", []), list)
                    else []
                ),
                "allowed_tools": (
                    list(getattr(item, "tools_allowed", []))
                    if isinstance(getattr(item, "tools_allowed", []), list)
                    else []
                ),
                "knowledge_sources": (
                    list(getattr(item, "knowledge_source_ids", []))
                    if isinstance(getattr(item, "knowledge_source_ids", []), list)
                    else []
                ),
            }
            for item in runtime_agents
        ]
        available_agent_descriptors.extend(
            [
                {
                    "id": str(temp.get("agent_id", "")),
                    "capabilities": list(temp.get("required_capabilities", [])),
                    "tags": ["temporary"],
                    "allowed_tools": list(temp.get("tools_allowed", [])),
                    "knowledge_sources": list(plan.get("selected_knowledge", [])),
                }
                for temp in plan.get("temporary_agents", [])
                if isinstance(temp, dict)
            ]
        )

        def _execute_agent(
            agent_id: str,
            task_prompt: str,
            task_context: dict[str, Any],
        ) -> dict[str, Any]:
            runtime_agent = self._agent_service.get_agent(
                agent_id,
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )

            payload = {
                "mission_id": mission_id,
                "goal": goal,
                "task_prompt": task_prompt,
                "task_context": task_context,
            }

            if runtime_agent is None:
                return {
                    "result": f"Temporary agent {agent_id} completed: {task_prompt}",
                    "reasoning": "Temporary execution agent synthesized output.",
                    "tool_outputs": [],
                    "memory_references": [],
                    "knowledge_references": [],
                    "confidence": 0.66,
                }

            response = self._llm_client.generate(
                prompt=(
                    f"Mission task: {task_prompt}\n"
                    f"Agent goal: {runtime_agent.goal}\n"
                    f"Agent instructions: {runtime_agent.instructions}\n"
                    "Return JSON with keys: result, reasoning, tool_outputs, "
                    "memory_references, knowledge_references, confidence.\n"
                    f"Payload: {json.dumps(payload, ensure_ascii=True)}"
                ),
                system=runtime_agent.system_prompt,
                model=runtime_agent.model or None,
                temperature=runtime_agent.temperature,
                format_json=True,
            )
            if isinstance(response, dict):
                output = dict(response)
            else:
                output = {
                    "result": str(response),
                    "reasoning": "",
                    "tool_outputs": [],
                    "memory_references": [],
                    "knowledge_references": [],
                    "confidence": 0.6,
                }
            output.setdefault("result", "")
            output.setdefault("reasoning", "")
            output.setdefault("tool_outputs", [])
            output.setdefault("memory_references", [])
            output.setdefault("knowledge_references", [])
            output.setdefault("confidence", 0.6)
            return output

        runtime_context = {
            "planner_agent_id": "autonomous-planner",
            "supervisor_agent_id": "autonomous-supervisor",
            "max_retries": 2,
            "retry_policy": "different_agent",
            "planned_tasks": planned_tasks,
            "shared_variables": {},
        }

        return self._multi_agent_runtime.run_goal(
            workflow_id="",
            execution_id=mission_id,
            conversation_id="",
            node_id="autonomous-mission",
            node_name="Autonomous Mission",
            goal=goal,
            runtime_context=runtime_context,
            available_agents=available_agent_descriptors,
            execute_agent=_execute_agent,
        )

    @staticmethod
    def _replan_after_failure(goal: str, plan: dict[str, Any]) -> dict[str, Any]:
        task_graph = [
            dict(item) for item in plan.get("task_graph", []) if isinstance(item, dict)
        ]
        if not task_graph:
            return {
                "task_graph": [],
                "reason": "No original task graph was available for replanning.",
            }

        replanned_tasks: list[dict[str, Any]] = []
        for item in task_graph:
            task_id = str(item.get("task_id", ""))
            title = str(item.get("title", "Task"))
            description = str(item.get("description", ""))
            replanned_tasks.append(
                {
                    "task_id": f"{task_id}-a",
                    "title": f"{title} (part A)",
                    "description": description,
                    "depends_on": list(item.get("depends_on", [])),
                }
            )
            replanned_tasks.append(
                {
                    "task_id": f"{task_id}-b",
                    "title": f"{title} (part B validation)",
                    "description": f"Validate and harden results for: {goal}",
                    "depends_on": [f"{task_id}-a"],
                }
            )

        return {
            "task_graph": replanned_tasks,
            "reason": "Original execution failed; tasks were split to improve recovery and validation.",
        }

    @staticmethod
    def _next_nodes_after_pending(
        workflow: Workflow, pending_node_id: str
    ) -> list[str]:
        return [
            edge.target_node_id
            for edge in workflow.edges
            if edge.source_node_id == pending_node_id
        ]

    def _require_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Workflow:
        workflow = self._repository.get_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if workflow is None:
            raise KeyError(f"Workflow not found: {workflow_id}")
        return workflow

    def _require_run(self, run_id: str) -> WorkflowRun:
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        return run

    @staticmethod
    def _build_nodes(payload_nodes: list[Any]) -> list[WorkflowNode]:
        return [
            WorkflowNode(
                id=node.id,
                node_type=node.node_type,
                name=node.name,
                agent_id=node.agent_id,
                x=node.x,
                y=node.y,
                config=dict(node.config),
            )
            for node in payload_nodes
        ]

    @staticmethod
    def _build_edges(payload_edges: list[Any]) -> list[WorkflowEdge]:
        return [
            WorkflowEdge(
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                label=edge.label,
                condition=edge.condition,
            )
            for edge in payload_edges
        ]
