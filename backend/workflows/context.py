"""Workflow execution context models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.agents.base import BaseAgent
    from backend.agents.context import AgentExecutionContext
    from backend.agents.tool_router import ToolRouter


@dataclass(slots=True)
class WorkflowContext:
    """Runtime context shared by workflow tasks."""

    agent_context: "AgentExecutionContext"
    agent: "BaseAgent"
    tool_router: "ToolRouter"
    metadata: dict[str, Any] = field(default_factory=dict)
    _cancelled: bool = False

    def cancel(self) -> None:
        """Mark the workflow execution as cancelled."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Return cancellation state."""
        return self._cancelled
