"""REST API for orchestration workflow lifecycle and execution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.agent_orchestration.models.workflow import (
    ValidationResponse,
    WorkflowCreateRequest,
    WorkflowDashboardResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowResponse,
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
