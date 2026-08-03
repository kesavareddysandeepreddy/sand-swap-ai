"""REST API for Agent Studio agent lifecycle operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.agent_studio.models.agent import (
    AgentCreateRequest,
    AgentDashboardResponse,
    AgentExecutionStepResponse,
    AgentResponse,
    AgentTestRequest,
    AgentTestRunResponse,
    AgentToolCallResponse,
    AgentUpdateRequest,
    AgentVersionCompareResponse,
    AgentVersionResponse,
)
from backend.api.dependencies import (
    AgentStudioServiceDependency,
    CurrentUserDependency,
    OwnershipContextDependency,
)
from backend.services import resolve_owner_id, resolve_project_id, resolve_workspace_id

router = APIRouter(prefix="/api/agents", tags=["agent-studio"])


@router.get("", response_model=list[AgentResponse])
def list_agents(
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> list[AgentResponse]:
    """List agents for the current ownership scope."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    return [
        AgentResponse.from_agent(agent)
        for agent in service.list_agents(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Fetch one agent by id."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    agent = service.get_agent(
        agent_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    return AgentResponse.from_agent(agent)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreateRequest,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Create a new agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    agent = service.create_agent(
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        payload=payload,
    )
    return AgentResponse.from_agent(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    payload: AgentUpdateRequest,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Update one agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        agent = service.update_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        ) from exc
    return AgentResponse.from_agent(agent)


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
def list_agent_versions(
    agent_id: str,
    service: AgentStudioServiceDependency,
) -> list[AgentVersionResponse]:
    """List version history for one agent."""
    return [
        AgentVersionResponse(
            id=version.id,
            agent_id=version.agent_id,
            version_number=version.version_number,
            change_summary=version.change_summary,
            snapshot=version.snapshot,
            created_at=version.created_at,
        )
        for version in service.list_versions(agent_id)
    ]


@router.get("/{agent_id}/versions/compare", response_model=AgentVersionCompareResponse)
def compare_agent_versions(
    agent_id: str,
    service: AgentStudioServiceDependency,
    left_version: int = Query(..., ge=1),
    right_version: int = Query(..., ge=1),
) -> AgentVersionCompareResponse:
    """Compare two versions for one agent."""
    try:
        return service.compare_versions(
            agent_id,
            left_version=left_version,
            right_version=right_version,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        ) from exc


@router.get("/{agent_id}/versions/{version_id}", response_model=AgentVersionResponse)
def get_agent_version(
    agent_id: str,
    version_id: str,
    service: AgentStudioServiceDependency,
) -> AgentVersionResponse:
    """Fetch a single version snapshot."""
    version = service.get_version(version_id)
    if version is None or version.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )
    return AgentVersionResponse(
        id=version.id,
        agent_id=version.agent_id,
        version_number=version.version_number,
        change_summary=version.change_summary,
        snapshot=version.snapshot,
        created_at=version.created_at,
    )


@router.post("/{agent_id}/versions/{version_id}/restore", response_model=AgentResponse)
def restore_agent_version(
    agent_id: str,
    version_id: str,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Restore an earlier version as the new active configuration."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        agent = service.restore_version(
            agent_id,
            version_id=version_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        ) from exc
    return AgentResponse.from_agent(agent)


@router.get("/{agent_id}/test-runs", response_model=list[AgentTestRunResponse])
def list_agent_test_runs(
    agent_id: str,
    service: AgentStudioServiceDependency,
) -> list[AgentTestRunResponse]:
    """List recorded test runs for one agent."""
    return [
        AgentTestRunResponse(
            id=test_run.id,
            agent_id=test_run.agent_id,
            prompt=test_run.prompt,
            reasoning=test_run.reasoning,
            tool_calls=[
                AgentToolCallResponse(
                    tool_name=str(item.get("tool_name", "")),
                    input=dict(item.get("input", {})),
                    success=bool(item.get("success", False)),
                    output=dict(item.get("output", {})),
                    duration_ms=float(item.get("duration_ms", 0.0)),
                    error=item.get("error"),
                )
                for item in test_run.tool_calls
            ],
            execution=[
                AgentExecutionStepResponse(
                    step_name=str(item.get("step_name", "")),
                    tool_name=str(item.get("tool_name", "")),
                    output=dict(item.get("output", {})),
                    duration_ms=float(item.get("duration_ms", 0.0)),
                )
                for item in test_run.execution
            ],
            final_answer=test_run.final_answer,
            success=test_run.success,
            error=test_run.error,
            timing_ms=test_run.timing_ms,
            created_at=test_run.created_at,
        )
        for test_run in service.list_test_runs(agent_id)
    ]


@router.post("/{agent_id}/test-runs", response_model=AgentTestRunResponse)
def run_agent_test_prompt(
    agent_id: str,
    payload: AgentTestRequest,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentTestRunResponse:
    """Run a real prompt through the configured agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    test_run = service.run_test_prompt(
        agent_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        payload=payload,
    )
    return AgentTestRunResponse(
        id=test_run.id,
        agent_id=test_run.agent_id,
        prompt=test_run.prompt,
        reasoning=test_run.reasoning,
        tool_calls=[
            AgentToolCallResponse(
                tool_name=str(item.get("tool_name", "")),
                input=dict(item.get("input", {})),
                success=bool(item.get("success", False)),
                output=dict(item.get("output", {})),
                duration_ms=float(item.get("duration_ms", 0.0)),
                error=item.get("error"),
            )
            for item in test_run.tool_calls
        ],
        execution=[
            AgentExecutionStepResponse(
                step_name=str(item.get("step_name", "")),
                tool_name=str(item.get("tool_name", "")),
                output=dict(item.get("output", {})),
                duration_ms=float(item.get("duration_ms", 0.0)),
            )
            for item in test_run.execution
        ],
        final_answer=test_run.final_answer,
        success=test_run.success,
        error=test_run.error,
        timing_ms=test_run.timing_ms,
        created_at=test_run.created_at,
    )


@router.get("/{agent_id}/dashboard", response_model=AgentDashboardResponse)
def get_agent_dashboard(
    agent_id: str,
    service: AgentStudioServiceDependency,
) -> AgentDashboardResponse:
    """Return dashboard metrics for one agent."""
    return service.get_dashboard(agent_id)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: str,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> dict[str, bool]:
    """Delete one agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    deleted = service.delete_agent(
        agent_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    return {"deleted": True}


@router.post("/{agent_id}/enable", response_model=AgentResponse)
def enable_agent(
    agent_id: str,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Enable one agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        agent = service.enable_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        ) from exc
    return AgentResponse.from_agent(agent)


@router.post("/{agent_id}/disable", response_model=AgentResponse)
def disable_agent(
    agent_id: str,
    service: AgentStudioServiceDependency,
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> AgentResponse:
    """Disable one agent."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        agent = service.disable_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        ) from exc
    return AgentResponse.from_agent(agent)
