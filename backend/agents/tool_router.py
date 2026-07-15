"""Tool router for selecting runtime tool dependencies."""

from __future__ import annotations

from typing import Any

from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlan
from backend.workflows.models import WorkflowTask


class ToolRouter:
    """Route planner-requested tools to concrete runtime services."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register_tool(self, name: str, tool: Any) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Tool name cannot be empty.")
        self._tools[normalized] = tool

    def discover(self) -> list[str]:
        return sorted(self._tools.keys())

    def lookup(self, name: str) -> Any | None:
        return self._tools.get(name)

    def select_tools(
        self,
        context: AgentExecutionContext,
        plan: AgentExecutionPlan,
    ) -> dict[str, Any]:
        _ = context
        selected: dict[str, Any] = {}
        for step in plan.steps:
            tool = self.lookup(step.tool)
            if tool is not None:
                selected[step.tool] = tool
        return selected

    def invoke_task(
        self,
        *,
        task: WorkflowTask,
        context: AgentExecutionContext,
    ) -> dict[str, Any]:
        """Execute a workflow task through a registered tool when possible."""
        if not task.tool_name:
            return {
                "status": "skipped",
                "reason": "task_has_no_tool",
                "task": task.name,
            }

        tool = self.lookup(task.tool_name)
        if tool is None:
            return {
                "status": "skipped",
                "reason": "tool_not_registered",
                "tool": task.tool_name,
                "action": task.action,
            }

        if task.tool_name == "MCP" and callable(getattr(tool, "call_tool", None)):
            if not task.mcp_server or not task.mcp_tool:
                return {
                    "status": "failed",
                    "reason": "invalid_mcp_task",
                    "tool": task.tool_name,
                    "action": task.action,
                }
            result = tool.call_tool(
                server_name=task.mcp_server,
                tool_name=task.mcp_tool,
                arguments=task.mcp_arguments,
            )
            return {
                "status": "failed" if result.is_error else "completed",
                "tool": task.tool_name,
                "action": task.action,
                "result": {
                    "server": result.server_name,
                    "tool": result.tool_name,
                    "content": result.content,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                },
            }

        execute_workflow_task = getattr(tool, "execute_workflow_task", None)
        if callable(execute_workflow_task):
            result = execute_workflow_task(task=task, context=context)
            return {
                "status": "completed",
                "tool": task.tool_name,
                "action": task.action,
                "result": result,
            }

        return {
            "status": "completed",
            "tool": task.tool_name,
            "action": task.action,
            "result": None,
        }

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "tools": self.discover(),
            "mcp": "extension_point_ready",
        }
