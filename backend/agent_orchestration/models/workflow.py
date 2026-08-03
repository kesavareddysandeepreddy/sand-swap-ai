"""Pydantic models for workflow orchestration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.agent_orchestration.domain.run import (
    AgentMessage,
    NodeExecutionRecord,
    WorkflowRun,
)
from backend.agent_orchestration.domain.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)


class WorkflowNodeModel(BaseModel):
    """Workflow node payload for transport boundaries."""

    id: str
    node_type: str
    name: str
    agent_id: str | None = None
    x: float = 0.0
    y: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, node: WorkflowNode) -> "WorkflowNodeModel":
        return cls(
            id=node.id,
            node_type=node.node_type,
            name=node.name,
            agent_id=node.agent_id,
            x=node.x,
            y=node.y,
            config=dict(node.config),
        )


class WorkflowEdgeModel(BaseModel):
    """Workflow edge payload for transport boundaries."""

    id: str
    source_node_id: str
    target_node_id: str
    label: str = ""
    condition: str = ""

    @classmethod
    def from_domain(cls, edge: WorkflowEdge) -> "WorkflowEdgeModel":
        return cls(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            label=edge.label,
            condition=edge.condition,
        )


class WorkflowCreateRequest(BaseModel):
    """Create-workflow request payload."""

    name: str = Field(..., min_length=1)
    description: str = ""
    enabled: bool = True
    nodes: list[WorkflowNodeModel] = Field(default_factory=list)
    edges: list[WorkflowEdgeModel] = Field(default_factory=list)
    execution_settings: dict[str, Any] = Field(default_factory=dict)
    shared_memory_settings: dict[str, Any] = Field(default_factory=dict)
    approval_settings: dict[str, Any] = Field(default_factory=dict)
    retry_settings: dict[str, Any] = Field(default_factory=dict)
    timeout_settings: dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdateRequest(BaseModel):
    """Update-workflow request payload."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    enabled: bool | None = None
    nodes: list[WorkflowNodeModel] | None = None
    edges: list[WorkflowEdgeModel] | None = None
    execution_settings: dict[str, Any] | None = None
    shared_memory_settings: dict[str, Any] | None = None
    approval_settings: dict[str, Any] | None = None
    retry_settings: dict[str, Any] | None = None
    timeout_settings: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    """Workflow transport response."""

    id: str
    name: str
    description: str
    enabled: bool
    owner_id: str
    workspace_id: str
    project_id: str
    nodes: list[WorkflowNodeModel]
    edges: list[WorkflowEdgeModel]
    execution_settings: dict[str, Any]
    shared_memory_settings: dict[str, Any]
    approval_settings: dict[str, Any]
    retry_settings: dict[str, Any]
    timeout_settings: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, workflow: Workflow) -> "WorkflowResponse":
        return cls(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            enabled=workflow.enabled,
            owner_id=workflow.owner_id,
            workspace_id=workflow.workspace_id,
            project_id=workflow.project_id,
            nodes=[WorkflowNodeModel.from_domain(item) for item in workflow.nodes],
            edges=[WorkflowEdgeModel.from_domain(item) for item in workflow.edges],
            execution_settings=dict(workflow.execution_settings),
            shared_memory_settings=dict(workflow.shared_memory_settings),
            approval_settings=dict(workflow.approval_settings),
            retry_settings=dict(workflow.retry_settings),
            timeout_settings=dict(workflow.timeout_settings),
            version=workflow.version,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )


class WorkflowExecutionRequest(BaseModel):
    """Execution request for one workflow run."""

    input_payload: dict[str, Any] = Field(default_factory=dict)
    wait_for_completion: bool = False


class WorkflowRunActionRequest(BaseModel):
    """Action request for approval/cancellation nodes."""

    action: str = Field(..., min_length=1)
    edited_input: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResponse(BaseModel):
    """Execution kickoff response."""

    run_id: str
    status: str


class WorkflowVersionResponse(BaseModel):
    """Workflow version snapshot response."""

    id: str
    workflow_id: str
    version_number: int
    change_summary: str
    snapshot: dict[str, Any]
    created_at: datetime


class NodeConfigRequest(BaseModel):
    """Node configuration update payload."""

    node_id: str
    name: str | None = None
    config: dict[str, Any] | None = None


class NodeExecutionRecordModel(BaseModel):
    """Node-level runtime result for run history."""

    node_id: str
    node_name: str
    node_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: float
    error: str
    output: dict[str, Any]

    @classmethod
    def from_domain(cls, record: NodeExecutionRecord) -> "NodeExecutionRecordModel":
        return cls(
            node_id=record.node_id,
            node_name=record.node_name,
            node_type=record.node_type,
            status=record.status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            duration_ms=record.duration_ms,
            error=record.error,
            output=dict(record.output),
        )


class AgentMessageModel(BaseModel):
    """Inter-agent communication record for execution monitor."""

    sender: str
    receiver: str
    timestamp: datetime
    payload: dict[str, Any]
    reasoning: str
    artifacts: list[dict[str, Any]]
    tool_outputs: list[dict[str, Any]]
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, message: AgentMessage) -> "AgentMessageModel":
        return cls(
            sender=message.sender,
            receiver=message.receiver,
            timestamp=message.timestamp,
            payload=dict(message.payload),
            reasoning=message.reasoning,
            artifacts=[dict(item) for item in message.artifacts],
            tool_outputs=[dict(item) for item in message.tool_outputs],
            metadata=dict(message.metadata),
        )


class WorkflowRunResponse(BaseModel):
    """Run-level response for execution monitor and history."""

    id: str
    workflow_id: str
    status: str
    input_payload: dict[str, Any]
    context: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: float
    error: str
    current_node_id: str
    pending_node_id: str
    cancel_requested: bool
    node_records: list[NodeExecutionRecordModel]
    messages: list[AgentMessageModel]
    artifacts: list[dict[str, Any]]
    logs: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, run: WorkflowRun) -> "WorkflowRunResponse":
        return cls(
            id=run.id,
            workflow_id=run.workflow_id,
            status=run.status,
            input_payload=dict(run.input_payload),
            context=dict(run.context),
            started_at=run.started_at,
            ended_at=run.ended_at,
            duration_ms=run.duration_ms,
            error=run.error,
            current_node_id=run.current_node_id,
            pending_node_id=run.pending_node_id,
            cancel_requested=run.cancel_requested,
            node_records=[
                NodeExecutionRecordModel.from_domain(item) for item in run.node_records
            ],
            messages=[AgentMessageModel.from_domain(item) for item in run.messages],
            artifacts=[dict(item) for item in run.artifacts],
            logs=[dict(item) for item in run.logs],
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class ValidationResponse(BaseModel):
    """Graph validation result payload."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowDashboardResponse(BaseModel):
    """Orchestration dashboard metrics payload."""

    running: int
    queued: int
    succeeded: int
    failed: int
    average_runtime_ms: float
    average_token_usage: float
    agent_usage: dict[str, int]
    most_active_workflows: list[dict[str, Any]]
