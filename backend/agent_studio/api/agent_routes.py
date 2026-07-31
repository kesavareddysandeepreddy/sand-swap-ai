"""REST API for Agent Studio agent lifecycle operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.agent_studio.models.agent import (
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
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
