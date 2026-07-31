"""Workflow task interfaces and generic task implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.workflows.context import WorkflowContext
from backend.workflows.models import WorkflowTask


class Task(ABC):
    """Abstract workflow task contract."""

    def __init__(self, definition: WorkflowTask) -> None:
        self._definition = definition

    @property
    def definition(self) -> WorkflowTask:
        """Return task definition metadata."""
        return self._definition

    @abstractmethod
    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        """Execute task and return structured output."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self, context: WorkflowContext) -> dict[str, Any]:
        """Rollback task side effects when available."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, object]:
        """Return task health details."""
        raise NotImplementedError


class ToolRouterTask(Task):
    """Task implementation that delegates execution through ToolRouter."""

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        cached_results = context.metadata.get("tool_results_by_step_id", {})
        if isinstance(cached_results, dict):
            cached = cached_results.get(self.definition.task_id)
            if isinstance(cached, dict):
                if cached.get("success") is False:
                    raise RuntimeError(f"Tool task failed: {self.definition.name}")
                return cached

        result = context.tool_router.invoke_task(
            task=self.definition,
            context=context.agent_context,
        )
        if result.get("status") == "failed":
            raise RuntimeError(f"Tool task failed: {self.definition.name}")
        return result

    def rollback(self, context: WorkflowContext) -> dict[str, Any]:
        _ = context
        return {
            "status": "noop",
            "task": self.definition.name,
            "reason": "rollback_not_implemented",
        }

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "task": self.definition.name,
            "type": "tool_router",
        }


class AgentResponseTask(Task):
    """Task that produces the final response via selected agent."""

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        tool_results = context.metadata.get("tool_results", [])
        if isinstance(tool_results, list) and tool_results:
            context.agent_context.metadata["tool_results"] = tool_results
            context.agent_context.metadata["tool_outputs_present"] = True
        response_text = context.agent.execute(context.agent_context)
        return {"response_text": response_text}

    def rollback(self, context: WorkflowContext) -> dict[str, Any]:
        _ = context
        return {
            "status": "noop",
            "task": self.definition.name,
            "reason": "response_generation_not_reversible",
        }

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "task": self.definition.name,
            "type": "agent_response",
        }
