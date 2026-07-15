"""Workflow planner utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from backend.workflows.models import Workflow, WorkflowTask


@dataclass(slots=True)
class _PlanStep:
    tool: str
    action: str
    reason: str = ""


class WorkflowPlanner:
    """Convert generic execution steps into workflow definitions."""

    def from_execution_plan(
        self,
        *,
        workflow_type: str,
        selected_agent: str,
        rationale: str,
        steps: list[_PlanStep],
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """Create a workflow from execution-plan style steps."""
        tasks: list[WorkflowTask] = []

        for index, step in enumerate(steps, start=1):
            task_kind = "agent_response" if step.tool == "LLM" else "tool_router"
            tasks.append(
                WorkflowTask(
                    task_id=f"task-{index}",
                    name=f"{step.tool}:{step.action}",
                    action=step.action,
                    tool_name=None if step.tool == "LLM" else step.tool,
                    max_retries=1 if step.tool == "LLM" else 0,
                    metadata={
                        "reason": step.reason,
                        "task_kind": task_kind,
                    },
                )
            )

        return Workflow(
            workflow_id=str(uuid4()),
            workflow_type=workflow_type,
            selected_agent=selected_agent,
            rationale=rationale,
            tasks=tasks,
            metadata=metadata or {},
        )

    def create_mcp_task(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> WorkflowTask:
        """Create a workflow task configured for MCP invocation."""
        return WorkflowTask(
            task_id=task_id or f"task-mcp-{uuid4().hex[:8]}",
            name=f"MCP:{server_name}.{tool_name}",
            action="call_tool",
            tool_name="MCP",
            mcp_server=server_name,
            mcp_tool=tool_name,
            mcp_arguments=arguments or {},
            metadata={"task_kind": "tool_router", "source": "mcp"},
        )
