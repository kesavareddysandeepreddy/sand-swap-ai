"""REST API for orchestration workflow lifecycle and execution."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.agent_orchestration.models.workflow import (
    AutonomousMissionRequest,
    AutonomousMissionResponse,
    AutonomousMissionStatusResponse,
    MissionControlDashboardResponse,
    MissionTemplateRequest,
    MissionTemplateResponse,
    ValidationResponse,
    WorkflowCreateRequest,
    WorkflowDashboardResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowResponse,
    WorkflowRetryRequest,
    WorkflowRunActionRequest,
    WorkflowRunResponse,
    WorkflowUpdateRequest,
    WorkflowVersionResponse,
)
from backend.api.dependencies import (
    CurrentUserDependency,
    OwnershipContextDependency,
    WorkflowServiceDependency,
)
from backend.services import resolve_owner_id, resolve_project_id, resolve_workspace_id

router = APIRouter(prefix="/api/workflows", tags=["agent-orchestration"])


@router.get("/dashboard", response_model=WorkflowDashboardResponse)
def workflow_dashboard(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowDashboardResponse:
    """Return run-level dashboard metrics for current scope."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    metrics = service.get_dashboard(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return WorkflowDashboardResponse(**metrics)


@router.get("/missions/dashboard", response_model=MissionControlDashboardResponse)
def mission_control_dashboard(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> MissionControlDashboardResponse:
    """Return autonomous mission-control dashboard metrics."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    metrics = service.mission_control_dashboard(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return MissionControlDashboardResponse(**metrics)


@router.post(
    "/missions",
    response_model=AutonomousMissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_autonomous_mission(
    payload: AutonomousMissionRequest,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AutonomousMissionResponse:
    """Create and optionally execute one autonomous mission from a natural-language goal."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        mission = service.create_autonomous_mission(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return AutonomousMissionResponse(**mission)


@router.get("/missions", response_model=list[AutonomousMissionResponse])
def list_autonomous_missions(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
    limit: int = Query(50, ge=1, le=500),
) -> list[AutonomousMissionResponse]:
    """List autonomous mission history in current ownership scope."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    missions = service.list_autonomous_missions(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        limit=limit,
    )
    return [AutonomousMissionResponse(**item) for item in missions]


@router.get("/missions/{mission_id}", response_model=AutonomousMissionResponse)
def get_autonomous_mission(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> AutonomousMissionResponse:
    """Return full autonomous mission payload by identifier."""
    try:
        mission = service.get_autonomous_mission(mission_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc
    return AutonomousMissionResponse(**mission)


@router.get(
    "/missions/{mission_id}/status",
    response_model=AutonomousMissionStatusResponse,
)
def get_autonomous_mission_status(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> AutonomousMissionStatusResponse:
    """Return concise autonomous mission status for polling."""
    try:
        payload = service.get_autonomous_mission_status(mission_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc
    return AutonomousMissionStatusResponse(**payload)


@router.get("/missions/{mission_id}/planner")
def get_autonomous_mission_planner_output(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, Any]:
    """Return planner output and graph explainability for one mission."""
    try:
        return {
            "mission_id": mission_id,
            "planner_output": service.get_autonomous_mission_planner_output(mission_id),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc


@router.get("/missions/{mission_id}/capability-scores")
def get_autonomous_mission_capability_scores(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, Any]:
    """Return detailed capability ranking and selected agents for each task."""
    try:
        return {
            "mission_id": mission_id,
            "scores": service.get_autonomous_mission_capability_scores(mission_id),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc


@router.get("/missions/{mission_id}/recommendations")
def get_autonomous_mission_recommendations(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, Any]:
    """Return autonomous recommendations for optimization and governance."""
    try:
        return {
            "mission_id": mission_id,
            "recommendations": service.get_autonomous_mission_recommendations(
                mission_id
            ),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc


@router.get("/missions/{mission_id}/temporary-agents")
def get_autonomous_mission_temporary_agents(
    mission_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, Any]:
    """Return temporary execution agents created for one mission."""
    try:
        return {
            "mission_id": mission_id,
            "temporary_agents": service.get_autonomous_mission_temporary_agents(
                mission_id
            ),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        ) from exc


@router.post("/mission-templates", response_model=MissionTemplateResponse)
def create_mission_template(
    payload: MissionTemplateRequest,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> MissionTemplateResponse:
    """Create one reusable autonomous execution template."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        created = service.create_mission_template(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return MissionTemplateResponse(**created)


@router.put("/mission-templates/{template_id}", response_model=MissionTemplateResponse)
def update_mission_template(
    template_id: str,
    payload: MissionTemplateRequest,
    service: WorkflowServiceDependency,
) -> MissionTemplateResponse:
    """Update one reusable mission template and increment version."""
    try:
        updated = service.update_mission_template(template_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission template not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return MissionTemplateResponse(**updated)


@router.get("/mission-templates", response_model=list[MissionTemplateResponse])
def list_mission_templates(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> list[MissionTemplateResponse]:
    """List reusable mission templates in ownership scope."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    templates = service.list_mission_templates(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return [MissionTemplateResponse(**item) for item in templates]


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> list[WorkflowResponse]:
    """List all workflows in current scope."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    workflows = service.list_workflows(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return [WorkflowResponse.from_domain(item) for item in workflows]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreateRequest,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowResponse:
    """Create a workflow."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        workflow = service.create_workflow(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowResponse.from_domain(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowResponse:
    """Get one workflow by id."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    workflow = service.get_workflow(
        workflow_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return WorkflowResponse.from_domain(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdateRequest,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowResponse:
    """Update one workflow."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        workflow = service.update_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowResponse.from_domain(workflow)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> dict[str, bool]:
    """Delete one workflow."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    deleted = service.delete_workflow(
        workflow_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return {"deleted": True}


@router.post("/{workflow_id}/validate", response_model=ValidationResponse)
def validate_workflow(
    workflow_id: str,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ValidationResponse:
    """Validate one workflow definition."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        validation = service.validate_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc
    return ValidationResponse(**validation)


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
def list_workflow_versions(
    workflow_id: str,
    service: WorkflowServiceDependency,
) -> list[WorkflowVersionResponse]:
    """List version snapshots for one workflow."""
    versions = service.list_workflow_versions(workflow_id)
    return [WorkflowVersionResponse(**item) for item in versions]


@router.get("/{workflow_id}/versions/compare")
def compare_workflow_versions(
    workflow_id: str,
    service: WorkflowServiceDependency,
    left_version: int = Query(..., ge=1),
    right_version: int = Query(..., ge=1),
) -> dict[str, object]:
    """Compare two workflow versions."""
    try:
        return service.compare_versions(
            workflow_id,
            left_version=left_version,
            right_version=right_version,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        ) from exc


@router.post(
    "/{workflow_id}/versions/{version_id}/restore", response_model=WorkflowResponse
)
def restore_workflow_version(
    workflow_id: str,
    version_id: str,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowResponse:
    """Restore workflow version snapshot as a new active version."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        restored = service.restore_version(
            workflow_id,
            version_id=version_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        ) from exc
    return WorkflowResponse.from_domain(restored)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(
    workflow_id: str,
    payload: WorkflowExecutionRequest,
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> WorkflowExecutionResponse:
    """Create and execute one workflow run."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        run = service.execute_workflow(
            workflow_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowExecutionResponse(run_id=run.id, status=run.status)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    workflow_id: str,
    service: WorkflowServiceDependency,
) -> list[WorkflowRunResponse]:
    """List execution history for one workflow."""
    return [
        WorkflowRunResponse.from_domain(item) for item in service.list_runs(workflow_id)
    ]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(
    run_id: str,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Get one run by id."""
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    return WorkflowRunResponse.from_domain(run)


@router.get("/runs/{run_id}/state", response_model=WorkflowRunResponse)
def get_workflow_run_state(
    run_id: str,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Return current execution state for one run."""
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    return WorkflowRunResponse.from_domain(run)


@router.get("/runs", response_model=list[WorkflowRunResponse])
def list_recent_runs(
    service: WorkflowServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
    limit: int = Query(20, ge=1, le=200),
) -> list[WorkflowRunResponse]:
    """List recent runs in scope across workflows."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    runs = service.list_recent_runs(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        limit=limit,
    )
    return [WorkflowRunResponse.from_domain(item) for item in runs]


@router.post("/runs/{run_id}/actions", response_model=WorkflowRunResponse)
def apply_run_action(
    run_id: str,
    payload: WorkflowRunActionRequest,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Apply approval action to a paused workflow run."""
    try:
        run = service.apply_run_action(run_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowRunResponse.from_domain(run)


@router.get("/runs/{run_id}/debugger")
def workflow_run_debugger(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return debugger payload for node-level execution inspection."""
    try:
        payload = service.get_run_debugger(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        ) from exc
    run = payload.get("run")
    workflow = payload.get("workflow")
    return {
        "run": WorkflowRunResponse.from_domain(run) if run is not None else None,
        "workflow": (
            WorkflowResponse.from_domain(workflow) if workflow is not None else None
        ),
        "nodes": payload.get("nodes", {}),
        "timeline": payload.get("timeline", []),
        "messages": payload.get("messages", []),
    }


@router.get("/runs/{run_id}/nodes/{node_id}")
def workflow_run_node_details(
    run_id: str,
    node_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return one node execution detail for debugger panel."""
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    record = next((item for item in run.node_records if item.node_id == node_id), None)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node execution record not found",
        )
    return {
        "run_id": run_id,
        "node_id": node_id,
        "record": {
            "node_id": record.node_id,
            "node_name": record.node_name,
            "node_type": record.node_type,
            "status": record.status,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "completed_at": (
                record.completed_at.isoformat() if record.completed_at else None
            ),
            "duration_ms": record.duration_ms,
            "error": record.error,
            "output": record.output,
        },
        "logs": [
            item
            for item in run.logs
            if str(item.get("metadata", {}).get("node_id", "")) == node_id
        ],
    }


@router.get("/runs/{run_id}/agent-registry")
def workflow_run_agent_registry(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return runtime agent registry snapshot."""
    try:
        registry = service.get_agent_registry(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    return {"run_id": run_id, "registry": registry}


@router.get("/runs/{run_id}/messages")
def workflow_run_messages(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return runtime structured message stream snapshot."""
    try:
        messages = service.get_agent_messages(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    return {"run_id": run_id, "messages": messages}


@router.get("/runs/{run_id}/timeline")
def workflow_run_timeline(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return execution timeline with runtime agent events."""
    try:
        timeline = service.get_execution_timeline(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    return {"run_id": run_id, "timeline": timeline}


@router.get("/runs/{run_id}/artifacts")
def workflow_run_artifacts(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return runtime artifact catalog for one run."""
    try:
        artifacts = service.get_execution_artifacts(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    return {"run_id": run_id, "artifacts": artifacts}


@router.get("/runs/{run_id}/supervisor")
def workflow_run_supervisor(
    run_id: str,
    service: WorkflowServiceDependency,
) -> dict[str, object]:
    """Return supervisor state for one run."""
    try:
        supervisor = service.get_supervisor_state(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    return {"run_id": run_id, "supervisor": supervisor}


@router.post("/runs/{run_id}/cancel", response_model=WorkflowRunResponse)
def cancel_run(
    run_id: str,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Cancel a queued or running workflow run."""
    try:
        run = service.cancel_run(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        ) from exc
    return WorkflowRunResponse.from_domain(run)


@router.post("/runs/{run_id}/pause", response_model=WorkflowRunResponse)
def pause_run(
    run_id: str,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Pause a queued or running execution."""
    try:
        run = service.pause_run(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowRunResponse.from_domain(run)


@router.post("/runs/{run_id}/resume", response_model=WorkflowRunResponse)
def resume_run(
    run_id: str,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Resume a paused execution."""
    try:
        run = service.resume_run(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowRunResponse.from_domain(run)


@router.post("/runs/{run_id}/retry", response_model=WorkflowRunResponse)
def retry_run(
    run_id: str,
    payload: WorkflowRetryRequest,
    service: WorkflowServiceDependency,
) -> WorkflowRunResponse:
    """Retry failed/canceled run using supervisor policy."""
    try:
        run = service.retry_run(
            run_id,
            policy=payload.policy,
            task_id=payload.task_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return WorkflowRunResponse.from_domain(run)


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    service: WorkflowServiceDependency,
) -> StreamingResponse:
    """Stream run updates as server-sent events."""

    async def event_stream() -> AsyncIterator[str]:
        seen = 0
        terminal_states = {"succeeded", "failed", "canceled"}
        while True:
            run = service.get_run(run_id)
            if run is None:
                payload: dict[str, object] = {
                    "event": "error",
                    "detail": "Run not found",
                }
                yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                return

            new_logs = run.logs[seen:]
            seen = len(run.logs)
            for log in new_logs:
                payload = {
                    "run_id": run.id,
                    "status": run.status,
                    "event": log,
                    "current_node_id": run.current_node_id,
                    "pending_node_id": run.pending_node_id,
                }
                yield f"event: workflow_update\ndata: {json.dumps(payload)}\n\n"

            if run.status in terminal_states:
                completed_payload = {
                    "run_id": run.id,
                    "status": run.status,
                    "duration_ms": run.duration_ms,
                    "error": run.error,
                }
                yield f"event: workflow_completed\ndata: {json.dumps(completed_payload)}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
