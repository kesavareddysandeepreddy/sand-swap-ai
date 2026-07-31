"""Pydantic models for Agent Studio API payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.agent_studio.domain.entities.agent import Agent


class AgentCreateRequest(BaseModel):
    """Create-agent request payload."""

    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    role: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    enabled: bool = True
    short_term_enabled: bool = True
    long_term_enabled: bool = True
    project_memory_enabled: bool = True
    tools_allowed: list[str] = Field(default_factory=list)
    connectors_allowed: list[str] = Field(default_factory=list)
    approval_required: bool = False
    max_iterations: int = Field(default=1, ge=1, le=100)
    timeout: int = Field(default=60, ge=1, le=3600)
    retry_policy: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class AgentUpdateRequest(BaseModel):
    """Update-agent request payload."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    role: str | None = Field(default=None, min_length=1)
    objective: str | None = Field(default=None, min_length=1)
    system_prompt: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    short_term_enabled: bool | None = None
    long_term_enabled: bool | None = None
    project_memory_enabled: bool | None = None
    tools_allowed: list[str] | None = None
    connectors_allowed: list[str] | None = None
    approval_required: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=100)
    timeout: int | None = Field(default=None, ge=1, le=3600)
    retry_policy: dict[str, object] | None = None
    tags: list[str] | None = None


class AgentResponse(BaseModel):
    """Serialized agent payload."""

    id: str
    name: str
    description: str
    role: str
    objective: str
    system_prompt: str
    enabled: bool
    short_term_enabled: bool
    long_term_enabled: bool
    project_memory_enabled: bool
    tools_allowed: list[str]
    connectors_allowed: list[str]
    approval_required: bool
    max_iterations: int
    timeout: int
    retry_policy: dict[str, object]
    tags: list[str]
    owner_id: str
    workspace_id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentResponse":
        """Convert a domain agent into an API response model."""
        return cls(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            role=agent.role,
            objective=agent.objective,
            system_prompt=agent.system_prompt,
            enabled=agent.enabled,
            short_term_enabled=agent.short_term_enabled,
            long_term_enabled=agent.long_term_enabled,
            project_memory_enabled=agent.project_memory_enabled,
            tools_allowed=list(agent.tools_allowed),
            connectors_allowed=list(agent.connectors_allowed),
            approval_required=agent.approval_required,
            max_iterations=agent.max_iterations,
            timeout=agent.timeout,
            retry_policy=dict(agent.retry_policy),
            tags=list(agent.tags),
            owner_id=agent.owner_id,
            workspace_id=agent.workspace_id,
            project_id=agent.project_id,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
