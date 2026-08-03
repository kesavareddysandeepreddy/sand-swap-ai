"""Pydantic models for Agent Studio API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.agent_studio.domain.entities.agent import Agent


class AgentCreateRequest(BaseModel):
    """Create-agent request payload."""

    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    instructions: str = Field(default="")
    system_prompt: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    goal: str = Field(default="")
    expected_output: str = Field(default="")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    model: str = Field(default="")
    enabled: bool = True
    color: str = Field(default="#2563eb")
    icon: str = Field(default="sparkles")
    capabilities: list[str] = Field(default_factory=list)
    agent_memory_enabled: bool = True
    project_memory_enabled: bool = True
    long_term_memory_enabled: bool = True
    conversation_memory_enabled: bool = True
    memory_importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_scope: str = Field(default="project")
    knowledge_source_ids: list[str] = Field(default_factory=list)
    document_library_ids: list[str] = Field(default_factory=list)
    github_repositories: list[str] = Field(default_factory=list)
    sharepoint_sites: list[str] = Field(default_factory=list)
    uploaded_document_ids: list[str] = Field(default_factory=list)
    project_knowledge_enabled: bool = True
    tools_allowed: list[str] = Field(default_factory=list)
    tool_permissions: dict[str, bool] = Field(default_factory=dict)
    connectors_allowed: list[str] = Field(default_factory=list)
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    approval_required: bool = False
    max_iterations: int = Field(default=1, ge=1, le=100)
    timeout: int = Field(default=60, ge=1, le=3600)
    retry_count: int = Field(default=0, ge=0, le=20)
    retry_policy: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    connected_agent_ids: list[str] = Field(default_factory=list)


class AgentUpdateRequest(BaseModel):
    """Update-agent request payload."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    instructions: str | None = None
    system_prompt: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    goal: str | None = None
    expected_output: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    model: str | None = None
    enabled: bool | None = None
    color: str | None = None
    icon: str | None = None
    capabilities: list[str] | None = None
    agent_memory_enabled: bool | None = None
    project_memory_enabled: bool | None = None
    long_term_memory_enabled: bool | None = None
    conversation_memory_enabled: bool | None = None
    memory_importance: float | None = Field(default=None, ge=0.0, le=1.0)
    memory_scope: str | None = None
    knowledge_source_ids: list[str] | None = None
    document_library_ids: list[str] | None = None
    github_repositories: list[str] | None = None
    sharepoint_sites: list[str] | None = None
    uploaded_document_ids: list[str] | None = None
    project_knowledge_enabled: bool | None = None
    tools_allowed: list[str] | None = None
    tool_permissions: dict[str, bool] | None = None
    connectors_allowed: list[str] | None = None
    execution_mode: Literal["sequential", "parallel"] | None = None
    approval_required: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=100)
    timeout: int | None = Field(default=None, ge=1, le=3600)
    retry_count: int | None = Field(default=None, ge=0, le=20)
    retry_policy: dict[str, object] | None = None
    tags: list[str] | None = None
    connected_agent_ids: list[str] | None = None


class AgentVersionResponse(BaseModel):
    """Serialized agent version payload."""

    id: str
    agent_id: str
    version_number: int
    change_summary: str
    snapshot: dict[str, Any]
    created_at: datetime


class AgentVersionCompareItem(BaseModel):
    """Single diff between two agent versions."""

    field: str
    before: Any
    after: Any


class AgentVersionCompareResponse(BaseModel):
    """Comparison result between two agent versions."""

    agent_id: str
    left_version: int
    right_version: int
    differences: list[AgentVersionCompareItem]


class AgentTestRequest(BaseModel):
    """Run-test prompt payload."""

    prompt: str = Field(..., min_length=1)


class AgentToolCallResponse(BaseModel):
    """Tool call result captured during a test run."""

    tool_name: str
    input: dict[str, Any]
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None


class AgentExecutionStepResponse(BaseModel):
    """Step-level execution record captured during a test run."""

    step_name: str
    tool_name: str
    output: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


class AgentTestRunResponse(BaseModel):
    """Serialized agent test run result."""

    id: str
    agent_id: str
    prompt: str
    reasoning: str
    tool_calls: list[AgentToolCallResponse]
    execution: list[AgentExecutionStepResponse]
    final_answer: str
    success: bool
    error: str | None
    timing_ms: float
    created_at: datetime


class AgentDashboardResponse(BaseModel):
    """Dashboard metrics for one agent."""

    agent_id: str
    status: str
    last_run_at: datetime | None
    success_rate: float
    average_runtime_ms: float
    memory_usage: str
    knowledge_source_count: int
    connected_agent_count: int
    total_versions: int


class AgentResponse(BaseModel):
    """Serialized agent payload."""

    id: str
    name: str
    description: str
    instructions: str
    system_prompt: str
    role: str
    goal: str
    expected_output: str
    temperature: float
    model: str
    enabled: bool
    color: str
    icon: str
    capabilities: list[str]
    agent_memory_enabled: bool
    project_memory_enabled: bool
    long_term_memory_enabled: bool
    conversation_memory_enabled: bool
    memory_importance: float
    memory_scope: str
    knowledge_source_ids: list[str]
    document_library_ids: list[str]
    github_repositories: list[str]
    sharepoint_sites: list[str]
    uploaded_document_ids: list[str]
    project_knowledge_enabled: bool
    tools_allowed: list[str]
    tool_permissions: dict[str, bool]
    connectors_allowed: list[str]
    execution_mode: str
    approval_required: bool
    max_iterations: int
    timeout: int
    retry_count: int
    retry_policy: dict[str, object]
    tags: list[str]
    connected_agent_ids: list[str]
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
            instructions=agent.instructions,
            system_prompt=agent.system_prompt,
            role=agent.role,
            goal=agent.goal,
            expected_output=agent.expected_output,
            temperature=agent.temperature,
            model=agent.model,
            enabled=agent.enabled,
            color=agent.color,
            icon=agent.icon,
            capabilities=list(agent.capabilities),
            agent_memory_enabled=agent.agent_memory_enabled,
            project_memory_enabled=agent.project_memory_enabled,
            long_term_memory_enabled=agent.long_term_memory_enabled,
            conversation_memory_enabled=agent.conversation_memory_enabled,
            memory_importance=agent.memory_importance,
            memory_scope=agent.memory_scope,
            knowledge_source_ids=list(agent.knowledge_source_ids),
            document_library_ids=list(agent.document_library_ids),
            github_repositories=list(agent.github_repositories),
            sharepoint_sites=list(agent.sharepoint_sites),
            uploaded_document_ids=list(agent.uploaded_document_ids),
            project_knowledge_enabled=agent.project_knowledge_enabled,
            tools_allowed=list(agent.tools_allowed),
            tool_permissions=dict(agent.tool_permissions),
            connectors_allowed=list(agent.connectors_allowed),
            execution_mode=agent.execution_mode,
            approval_required=agent.approval_required,
            max_iterations=agent.max_iterations,
            timeout=agent.timeout,
            retry_count=agent.retry_count,
            retry_policy=dict(agent.retry_policy),
            tags=list(agent.tags),
            connected_agent_ids=list(agent.connected_agent_ids),
            owner_id=agent.owner_id,
            workspace_id=agent.workspace_id,
            project_id=agent.project_id,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
