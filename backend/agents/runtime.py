"""Runtime orchestrator for selecting and executing agents."""

from __future__ import annotations

from backend.agents.context import AgentExecutionContext
from backend.agents.execution import AgentExecutor
from backend.agents.models import AgentExecutionResult
from backend.agents.planner import PlannerAgent
from backend.agents.registry import AgentRegistry
from backend.agents.tool_router import ToolRouter
from backend.core.logging.logger import LoggerFactory


class AgentRuntime:
    """Select an agent, create plan, execute, and return structured result."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        planner: PlannerAgent,
        tool_router: ToolRouter,
        executor: AgentExecutor,
    ) -> None:
        self.registry = registry
        self.planner = planner
        self.tool_router = tool_router
        self.executor = executor
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
