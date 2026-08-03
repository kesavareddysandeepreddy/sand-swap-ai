"""Application service for workflow orchestration operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

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
    WorkflowCreateRequest,
    WorkflowExecutionRequest,
    WorkflowRunActionRequest,
    WorkflowUpdateRequest,
)
from backend.agent_orchestration.planner.validator import WorkflowValidator
from backend.agent_orchestration.repository.workflow_repository import (
    WorkflowRepository,
)
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
                "owner_id": owner_id,
                "workspace_id": workspace_id,
                "project_id": project_id,
            },
            status=WorkflowRunStatus.QUEUED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
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

        user_payload = {
            "node": {
                "id": node.id,
                "name": node.name,
                "config": dict(node.config),
            },
            "context": dict(context),
        }
        prompt = (
            f"Agent task: {node.name}\n"
            f"Agent goal: {agent.goal}\n"
            f"Agent instructions: {agent.instructions}\n"
            "Return JSON with keys: result, reasoning, tool_outputs.\n"
            f"Payload: {json.dumps(user_payload, ensure_ascii=True)}"
        )
        response = self._llm_client.generate(
            prompt=prompt,
            system=agent.system_prompt,
            model=agent.model or None,
            temperature=agent.temperature,
            format_json=True,
        )
        if isinstance(response, dict):
            output = dict(response)
        else:
            output = {"result": str(response), "reasoning": "", "tool_outputs": []}
        output.setdefault("result", "")
        output.setdefault("reasoning", "")
        output.setdefault("tool_outputs", [])
        output["agent_id"] = node.agent_id
        output["agent_name"] = agent.name
        return output

    def _should_cancel(self, run_id: str) -> bool:
        latest = self._repository.get_run(run_id)
        if latest is None:
            return True
        return latest.cancel_requested

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
