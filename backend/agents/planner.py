"""Planner component for generic agent runtime."""

from __future__ import annotations

from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlan, AgentExecutionPlanStep
from backend.core.logging.logger import LoggerFactory
from backend.workflows.models import Workflow
from backend.workflows.planner import WorkflowPlanner


class PlannerAgent:
    """Generate execution plans from intent and available context."""

    def __init__(self) -> None:
        self.logger = LoggerFactory.get_logger("PlannerAgent")
        self.workflow_planner = WorkflowPlanner()

    def plan(self, context: AgentExecutionContext, selected_agent: str) -> Workflow:
        steps: list[AgentExecutionPlanStep] = []
        mcp_requests: list[dict[str, str]] = []

        mcp_tools = context.metadata.get("mcp_tools", [])
        if isinstance(mcp_tools, list):
            for entry in mcp_tools:
                if not isinstance(entry, dict):
                    continue
                server = str(entry.get("server", "")).strip()
                tool = str(entry.get("tool", "")).strip()
                if server and tool:
                    mcp_requests.append({"server": server, "tool": tool})

        user_prompt_lower = context.user_prompt.lower()
        if not mcp_requests and "mcp:" in user_prompt_lower:
            token = user_prompt_lower.split("mcp:", maxsplit=1)[1].strip().split()[0]
            if "." in token:
                server, tool = token.split(".", maxsplit=1)
                server = server.strip()
                tool = tool.strip()
                if server and tool:
                    mcp_requests.append({"server": server, "tool": tool})

        if context.knowledge_object_ids:
            steps.append(
                AgentExecutionPlanStep(
                    tool="KnowledgeService",
                    action="inspect_knowledge_objects",
                    reason="Knowledge objects are present in conversation scope.",
                )
            )
        if context.vision_context.strip() or context.knowledge_context.strip():
            steps.append(
                AgentExecutionPlanStep(
                    tool="VisionProvider",
                    action="reuse_vision_context",
                    reason="Vision-derived context is available.",
                )
            )
        if context.memory_context:
            steps.append(
                AgentExecutionPlanStep(
                    tool="Memory",
                    action="use_relevant_memory",
                    reason="Relevant memory records were retrieved.",
                )
            )
        if context.rag_context:
            steps.append(
                AgentExecutionPlanStep(
                    tool="RAG",
                    action="use_retrieved_chunks",
                    reason="RAG context is available for grounding.",
                )
            )

        steps.append(
            AgentExecutionPlanStep(
                tool="LLM",
                action="generate_response",
                reason="Produce final assistant response.",
            )
        )

        plan = AgentExecutionPlan(
            selected_agent=selected_agent,
            rationale="Generic planner assembled tool usage from available context.",
            steps=steps,
            metadata={
                "user_prompt_length": len(context.user_prompt),
                "knowledge_count": len(context.knowledge_object_ids),
                "memory_count": len(context.memory_context),
                "rag_count": len(context.rag_context),
            },
        )
        workflow = self.workflow_planner.from_execution_plan(
            workflow_type="agent_execution",
            selected_agent=selected_agent,
            rationale=plan.rationale,
            steps=plan.steps,
            metadata=plan.metadata,
        )

        for request in mcp_requests:
            workflow.tasks.insert(
                0,
                self.workflow_planner.create_mcp_task(
                    server_name=request["server"],
                    tool_name=request["tool"],
                ),
            )
        self.logger.debug(
            "Workflow generated agent=%s tasks=%s",
            selected_agent,
            [task.name for task in workflow.tasks],
        )
        return workflow

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "component": "planner",
            "workflow_planner": "enabled",
        }
