"""Runtime orchestrator for selecting and executing agents."""

from __future__ import annotations

from backend.agents.context import AgentExecutionContext
from backend.agents.execution import AgentExecutor
from backend.agents.models import AgentExecutionResult
from backend.agents.planner import PlannerAgent
from backend.agents.registry import AgentRegistry
from backend.agents.tool_router import ToolRouter
from backend.core.logging.logger import LoggerFactory
from backend.workers.base_worker import BaseWorker


class AgentRuntime:
    """Select an agent, create plan, execute, and return structured result."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        planner: PlannerAgent,
        tool_router: ToolRouter,
        executor: AgentExecutor,
        worker: BaseWorker | None = None,
    ) -> None:
        self.registry = registry
        self.planner = planner
        self.tool_router = tool_router
        self.executor = executor
        self.worker = worker
        self.logger = LoggerFactory.get_logger("AgentRuntime")

    def _select_agent(self, context: AgentExecutionContext):
        for agent in self.registry.discover():
            if agent.can_handle(context):
                return agent
        fallback = self.registry.lookup("general_chat_agent")
        if fallback is not None:
            return fallback
        raise RuntimeError("No registered agent can handle the execution context.")

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        agent = self._select_agent(context)
        self.logger.debug("Agent selected name=%s", agent.name())

        if self.worker is not None:
            response_text = self.worker.execute(context, agent=agent)
            plan = context.metadata.get("workflow_plan")
            workflow_id = context.metadata.get("workflow_id")
            workflow_status = context.metadata.get("workflow_status")
            execution_time = context.metadata.get("workflow_execution_time")
            task_count = context.metadata.get("workflow_task_count")
            selected_tools = context.metadata.get("selected_tool_metadata", [])

            return AgentExecutionResult(
                agent_name=agent.name(),
                response_text=response_text,
                plan=plan,
                tools_invoked=(
                    list(selected_tools) if isinstance(selected_tools, list) else []
                ),
                execution_time=(
                    float(execution_time)
                    if isinstance(execution_time, (int, float))
                    else 0.0
                ),
                metadata={
                    "selected_tool_count": (
                        len(selected_tools) if isinstance(selected_tools, list) else 0
                    ),
                    "workflow_id": workflow_id,
                    "workflow_status": workflow_status,
                    "task_count": int(task_count) if isinstance(task_count, int) else 0,
                    "execution_trace_id": context.metadata.get("execution_trace_id"),
                },
            )

        plan = self.planner.plan(context, selected_agent=agent.name())
        self.logger.debug(
            "Workflow generated agent=%s tasks=%s",
            agent.name(),
            [task.name for task in plan.tasks],
        )

        return self.executor.execute(
            agent=agent,
            context=context,
            plan=plan,
            tool_router=self.tool_router,
        )

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "planner": self.planner.health(),
            "registry": self.registry.health(),
            "tool_router": self.tool_router.health(),
        }
