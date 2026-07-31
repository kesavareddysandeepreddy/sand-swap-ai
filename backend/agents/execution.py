"""Execution engine for agent runtime plans."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionResult
from backend.agents.tool_router import ToolRouter
from backend.core.logging.logger import LoggerFactory
from backend.workflows.context import WorkflowContext
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.models import Workflow
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry


class AgentExecutor:
    """Execute a workflow with a selected agent and routed tools."""

    def __init__(self, workflow_engine: WorkflowEngine | None = None) -> None:
        self.workflow_engine = workflow_engine or WorkflowEngine(
            registry=WorkflowRegistry(),
            executor=WorkflowExecutor(),
            queue=InMemoryWorkflowQueue(),
        )
        self.logger = LoggerFactory.get_logger("AgentExecutor")

    def execute(
        self,
        *,
        agent: BaseAgent,
        context: AgentExecutionContext,
        plan: Workflow,
        tool_router: ToolRouter,
    ) -> AgentExecutionResult:
        workflow_context = WorkflowContext(
            agent_context=context,
            agent=agent,
            tool_router=tool_router,
            metadata={
                "tool_results": context.metadata.get("tool_results", []),
                "tool_results_by_step_id": context.metadata.get(
                    "tool_results_by_step_id", {}
                ),
            },
        )
        workflow_result = self.workflow_engine.execute(plan, workflow_context)

        tool_names = sorted(
            {
                task.tool_name
                for task in plan.tasks
                if task.tool_name and task.tool_name.strip()
            }
        )
        self.logger.debug(
            "Tools invoked agent=%s tools=%s workflow_status=%s",
            agent.name(),
            tool_names,
            workflow_result.status,
        )

        return AgentExecutionResult(
            agent_name=agent.name(),
            response_text=workflow_result.response_text,
            plan=plan,
            tools_invoked=tool_names,
            execution_time=workflow_result.execution_time,
            metadata={
                "selected_tool_count": len(tool_names),
                "workflow_id": workflow_result.workflow_id,
                "workflow_status": workflow_result.status,
                "task_count": len(workflow_result.task_results),
                "tool_results": workflow_result.metadata.get("tool_results", []),
            },
        )
