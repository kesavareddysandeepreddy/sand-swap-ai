"""Universal worker that orchestrates existing planning and workflow components."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.planner import PlannerAgent
from backend.agents.tool_router import ToolRouter
from backend.core.logging.logger import LoggerFactory
from backend.execution.recorder import ExecutionRecorder
from backend.execution.tracker import ExecutionTracker
from backend.execution_graph import (
    ExecutionGraphBuilder,
    ExecutionGraphSerializer,
    graph_runtime_metadata,
)
from backend.project_memory.archive_manager import ArchiveManager
from backend.project_memory.checkpoint import ConversationCheckpointEngine
from backend.task_planner.planner import TaskPlanner
from backend.tool_execution import ToolExecutor, ToolInvocationEngine, ToolResolver
from backend.tool_sdk.registry import ToolRegistry
from backend.tools.capability_registry import CapabilityRegistry
from backend.workers.base_worker import BaseWorker
from backend.workflows.context import WorkflowContext
from backend.workflows.engine import WorkflowEngine


class UniversalWorker(BaseWorker):
    """Generic orchestration worker without domain-specific business logic."""

    def __init__(
        self,
        *,
        planner: PlannerAgent,
        workflow_engine: WorkflowEngine,
        tool_router: ToolRouter,
        agent: BaseAgent,
        capability_registry: CapabilityRegistry | None = None,
        execution_recorder: ExecutionRecorder | None = None,
        checkpoint_engine: ConversationCheckpointEngine | None = None,
        archive_manager: ArchiveManager | None = None,
        task_planner: TaskPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_invocation_engine: ToolInvocationEngine | None = None,
    ) -> None:
        self.planner = planner
        self.workflow_engine = workflow_engine
        self.tool_router = tool_router
        self.agent = agent
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.execution_recorder = execution_recorder or ExecutionRecorder()
        self.checkpoint_engine = checkpoint_engine
        self.archive_manager = archive_manager
        self.task_planner = task_planner or TaskPlanner()
        self.tool_registry = tool_registry or ToolRegistry(
            capability_registry=self.capability_registry
        )
        self.tool_executor = tool_executor or ToolExecutor()
        self.tool_invocation_engine = tool_invocation_engine or ToolInvocationEngine(
            resolver=ToolResolver(
                capability_registry=self.capability_registry,
                tool_registry=self.tool_registry,
                tool_router=self.tool_router,
            ),
            executor=self.tool_executor,
        )
        self.logger = LoggerFactory.get_logger("UniversalWorker")

    @staticmethod
    def _capabilities_for_tool(task_tool_name: str | None) -> list[str]:
        if not task_tool_name:
            return []
        mapping = {
            "KnowledgeService": ["knowledge"],
            "VisionProvider": ["vision"],
            "Memory": ["memory"],
            "RAG": ["rag"],
            "FilesystemTool": ["filesystem"],
            "PythonTool": ["python"],
            "RESTTool": ["rest"],
            "MCP": ["mcp"],
            "WorkflowEngine": ["workflow"],
        }
        return mapping.get(task_tool_name, [task_tool_name.lower()])

    def _select_tools(
        self, context: AgentExecutionContext, workflow: object
    ) -> list[str]:
        _ = context
        required_capabilities: list[str] = []
        tasks = getattr(workflow, "tasks", [])
        if isinstance(tasks, list):
            for task in tasks:
                tool_name = getattr(task, "tool_name", None)
                for capability in self._capabilities_for_tool(tool_name):
                    if capability not in required_capabilities:
                        required_capabilities.append(capability)

        selected: list[str] = []
        for capability in required_capabilities:
            matches = self.capability_registry.find_by_capability(capability)
            if not matches:
                continue
            chosen = matches[0].name
            if chosen not in selected:
                selected.append(chosen)
        return selected

    def name(self) -> str:
        return "universal_worker"

    def description(self) -> str:
        return "Universal worker that delegates to planner, workflow engine, and tool router."

    def execute(
        self,
        context: AgentExecutionContext,
        agent: BaseAgent | None = None,
    ) -> str:
        active_agent = agent or self.agent
        request_id = context.metadata.get("request_id")
        if request_id is not None:
            request_id = str(request_id)

        trace = self.execution_recorder.create_trace(
            worker_name=self.name(),
            request_id=request_id,
        )
        trace.metadata.update(
            {
                "task_plan": {},
                "inferred_capabilities": [],
                "estimated_cost": 0.0,
                "complexity": "low",
                "execution_state": "planning",
            }
        )
        context.metadata["execution_trace_id"] = trace.trace_id
        tracker = ExecutionTracker(trace)

        try:
            with tracker.step("Worker Start"):
                pass

            with tracker.step("Planner"):
                task_plan = self.task_planner.plan(context.user_prompt)
                task_plan_metadata = task_plan.as_metadata()
                execution_graph = ExecutionGraphBuilder.from_task_plan(task_plan)
                execution_graph_metadata = ExecutionGraphSerializer.to_metadata(
                    execution_graph
                )
                runtime_graph_metadata = graph_runtime_metadata(execution_graph)
                checkpoint_placeholders = {
                    "planning_checkpoint": {
                        "status": "pending",
                        "description": "Checkpoint before execution starts.",
                    },
                    "pre_tool_checkpoint": {
                        "status": "pending",
                        "description": "Checkpoint before tool invocation.",
                    },
                    "post_workflow_checkpoint": {
                        "status": "pending",
                        "description": "Checkpoint after workflow completion.",
                    },
                }
                checkpoint_placeholders["runtime"] = runtime_graph_metadata[
                    "checkpoint_state"
                ]
                task_plan_metadata["execution_graph"] = execution_graph_metadata
                task_plan_metadata["checkpoint_placeholders"] = checkpoint_placeholders
                task_plan_metadata["graph_runtime"] = runtime_graph_metadata
                context.metadata["task_plan"] = task_plan_metadata
                context.metadata["execution_graph"] = execution_graph_metadata
                context.metadata["checkpoint_placeholders"] = checkpoint_placeholders
                context.metadata["graph_runtime"] = runtime_graph_metadata
                context.metadata["estimated_cost"] = task_plan.estimated_total_cost
                context.metadata["complexity"] = task_plan.overall_complexity
                context.metadata["execution_state"] = "planning"

                workflow = self.planner.plan(
                    context, selected_agent=active_agent.name()
                )
                context.metadata["workflow_plan"] = workflow
                context.metadata["selected_agent"] = active_agent.name()
                context.metadata["inferred_capabilities"] = list(
                    task_plan.inferred_capabilities
                )

                trace.metadata.update(
                    {
                        "task_plan": task_plan_metadata,
                        "execution_graph": execution_graph_metadata,
                        "checkpoint_placeholders": checkpoint_placeholders,
                        "graph_runtime": runtime_graph_metadata,
                        "retries": runtime_graph_metadata["retries"],
                        "queue_duration_ms": runtime_graph_metadata[
                            "queue_duration_ms"
                        ],
                        "execution_duration_ms": runtime_graph_metadata[
                            "execution_duration_ms"
                        ],
                        "node_status": runtime_graph_metadata["node_status"],
                        "checkpoint_state": runtime_graph_metadata["checkpoint_state"],
                        "inferred_capabilities": list(task_plan.inferred_capabilities),
                        "estimated_cost": task_plan.estimated_total_cost,
                        "complexity": task_plan.overall_complexity,
                        "execution_state": "planning",
                    }
                )

            with tracker.step("Capability Selection"):
                selected_tools = self._select_tools(context, workflow)
                context.metadata["selected_tool_metadata"] = selected_tools

            trace.metadata["execution_state"] = "executing"
            context.metadata["execution_state"] = "executing"

            with tracker.step("Tool Invocation"):
                tool_results = self.tool_invocation_engine.execute(
                    task_plan,
                    WorkflowContext(
                        agent_context=context,
                        agent=active_agent,
                        tool_router=self.tool_router,
                        metadata={"selected_tools": selected_tools},
                    ),
                    trace,
                )
                tool_results_metadata = [
                    result.as_metadata() for result in tool_results
                ]
                context.metadata["tool_results"] = tool_results_metadata
                context.metadata["tool_results_by_step_id"] = {
                    result.step_id: result.as_metadata() for result in tool_results
                }
                context.metadata["tool_results_by_tool_name"] = {
                    result.tool_name: result.as_metadata() for result in tool_results
                }
                trace.metadata["tool_results"] = tool_results_metadata
                trace.metadata["tool_results_by_step_id"] = context.metadata[
                    "tool_results_by_step_id"
                ]
                trace.metadata["tool_results_by_tool_name"] = context.metadata[
                    "tool_results_by_tool_name"
                ]
                workflow.metadata["tool_results"] = tool_results_metadata
                workflow.metadata["tool_results_by_step_id"] = context.metadata[
                    "tool_results_by_step_id"
                ]
                workflow.metadata["tool_results_by_tool_name"] = context.metadata[
                    "tool_results_by_tool_name"
                ]
                if tool_results_metadata:
                    context.prompt = "\n\n".join(
                        [
                            context.prompt,
                            "Tool Outputs:",
                            trace.metadata.get("tool_results_summary")
                            or self.tool_invocation_engine._summarize_tools(
                                tool_results
                            ),
                            "Execution Summary:",
                            f"Resolved {len(tool_results_metadata)} tool result(s) before workflow execution.",
                        ]
                    )

            with tracker.step("Workflow Execution"):
                workflow_context = WorkflowContext(
                    agent_context=context,
                    agent=active_agent,
                    tool_router=self.tool_router,
                    metadata={
                        "selected_tools": selected_tools,
                        "tool_results": context.metadata.get("tool_results", []),
                        "tool_results_by_step_id": context.metadata.get(
                            "tool_results_by_step_id", {}
                        ),
                    },
                )
                result = self.workflow_engine.execute(workflow, workflow_context)
                context.metadata["workflow_id"] = result.workflow_id
                context.metadata["workflow_status"] = result.status
                context.metadata["workflow_execution_time"] = result.execution_time
                context.metadata["workflow_task_count"] = len(result.task_results)
                context.metadata["workflow_result_metadata"] = result.metadata

            with tracker.step(
                "Final Response",
                metadata={"response_length": len(result.response_text)},
            ):
                response_text = result.response_text

            with tracker.step("Worker Finish"):
                pass

            trace.finish()
            trace.metadata["execution_state"] = "completed"
            context.metadata["execution_state"] = "completed"
            self._run_memory_hooks(context)
            return response_text
        except Exception:  # noqa: BLE001
            trace.metadata["execution_state"] = "failed"
            context.metadata["execution_state"] = "failed"
            if trace.completed_at is None:
                trace.finish()
            raise

    def _run_memory_hooks(self, context: AgentExecutionContext) -> None:
        project_id = context.project_id
        if not project_id:
            return

        conversation_id = context.conversation.id
        messages = [message.content for message in context.conversation.messages]
        checkpoint_summary = None

        if self.checkpoint_engine is not None:
            try:
                checkpoint_summary = self.checkpoint_engine.create_checkpoint(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    messages=messages,
                )
            except Exception:  # noqa: BLE001
                self.logger.exception("Checkpoint engine invocation failed")

        if self.archive_manager is not None and checkpoint_summary is None:
            try:
                self.archive_manager.archive(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    messages=messages,
                )
            except Exception:  # noqa: BLE001
                self.logger.exception("Archive manager invocation failed")
