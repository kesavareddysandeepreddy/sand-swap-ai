"""Data models for generic agent runtime planning and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.workflows.models import Workflow


@dataclass(slots=True)
class AgentExecutionPlanStep:
    """One planner-produced execution step."""

    tool: str
    action: str
    reason: str = ""


@dataclass(slots=True)
class AgentExecutionPlan:
    """Planner output consumed by the runtime executor."""

    selected_agent: str
    rationale: str = ""
    steps: list[AgentExecutionPlanStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentExecutionResult:
    """Structured runtime result returned to callers."""

    agent_name: str
    response_text: str
    plan: Workflow
    tools_invoked: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
