"""Core workflow data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowStatus = Literal["completed", "failed", "cancelled"]
TaskStatus = Literal["completed", "failed", "cancelled", "skipped"]


@dataclass(slots=True)
class WorkflowTask:
    """Serializable task definition used by workflow runtime."""

    task_id: str
    name: str
    action: str
    tool_name: str | None = None
    mcp_server: str | None = None
    mcp_tool: str | None = None
    mcp_arguments: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Workflow:
    """Workflow plan composed of ordered task definitions."""

    workflow_id: str
    workflow_type: str
    selected_agent: str
    rationale: str = ""
    tasks: list[WorkflowTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowTaskResult:
    """Execution result for a single workflow task."""

    task_id: str
    task_name: str
    status: TaskStatus
    attempts: int = 1
    error: str | None = None
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowResult:
    """Structured output returned by workflow execution."""

    workflow_id: str
    workflow_type: str
    selected_agent: str
    status: WorkflowStatus
    task_results: list[WorkflowTaskResult] = field(default_factory=list)
    response_text: str = ""
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
