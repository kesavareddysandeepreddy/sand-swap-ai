from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlan
from backend.agents.planner import PlannerAgent
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.execution.recorder import ExecutionRecorder
from backend.tools.capability_registry import CapabilityRegistry
from backend.tools.tool_metadata import ToolMetadata
from backend.workers.registry import WorkerRegistry
from backend.workers.universal_worker import UniversalWorker
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.model = "test-model"

    def generate(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return "worker response"


class DummyAgent(BaseAgent):
    def __init__(self, response: str = "dummy") -> None:
        self._response = response

    def name(self) -> str:
        return "dummy_agent"

    def description(self) -> str:
        return "dummy"

    def can_handle(self, context: AgentExecutionContext) -> bool:
        _ = context
        return True

    def plan(self, context: AgentExecutionContext) -> AgentExecutionPlan:
        _ = context
        return AgentExecutionPlan(selected_agent=self.name())

    def execute(self, context: AgentExecutionContext) -> str:
        _ = context
        return self._response

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


def _context() -> AgentExecutionContext:
    conversation = Conversation(user_id="u1", id="u1:worker")
    return AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt="hello",
        prompt="rendered prompt",
        system_prompt="system prompt",
        model="model-a",
        metadata={"temperature": 0.2},
    )


def test_worker_registry_register_and_lookup() -> None:
    registry = WorkerRegistry()
    capability_registry = CapabilityRegistry()
    execution_recorder = ExecutionRecorder()
    worker = UniversalWorker(
        planner=PlannerAgent(),
        workflow_engine=WorkflowEngine(
            registry=WorkflowRegistry(),
            executor=WorkflowExecutor(),
            queue=InMemoryWorkflowQueue(),
        ),
        tool_router=ToolRouter(),
        agent=DummyAgent(response="worker response"),
        capability_registry=capability_registry,
        execution_recorder=execution_recorder,
    )

    registry.register(worker)

    assert registry.lookup("universal_worker") is worker
    assert [item.name() for item in registry.discover()] == ["universal_worker"]


def test_universal_worker_executes_via_planner_and_workflow_engine() -> None:
    capability_registry = CapabilityRegistry()
    execution_recorder = ExecutionRecorder()
    capability_registry.register_tool(
        ToolMetadata(
            name="Memory",
            description="Memory tool",
            capabilities=["memory"],
            priority=5,
        )
    )
    capability_registry.register_tool(
        ToolMetadata(
            name="RAG",
            description="RAG tool",
            capabilities=["rag"],
            priority=5,
        )
    )
    worker = UniversalWorker(
        planner=PlannerAgent(),
        workflow_engine=WorkflowEngine(
            registry=WorkflowRegistry(),
            executor=WorkflowExecutor(),
            queue=InMemoryWorkflowQueue(),
        ),
        tool_router=ToolRouter(),
        agent=DummyAgent(response="worker response"),
        capability_registry=capability_registry,
        execution_recorder=execution_recorder,
    )

    context = _context()
    context.memory_context = [{"key": "k", "value": "v"}]
    context.rag_context = [{"chunk": "doc"}]

    result = worker.execute(context)

    assert result == "worker response"
    assert context.metadata["selected_tool_metadata"] == ["Memory", "RAG"]
    assert isinstance(context.metadata["task_plan"], dict)
    assert "steps" in context.metadata["task_plan"]
    assert isinstance(context.metadata["inferred_capabilities"], list)
    trace_id = context.metadata["execution_trace_id"]
    trace = execution_recorder.get_trace(trace_id)
    assert trace is not None
    stages = [step.stage for step in trace.steps]
    assert stages[:3] == ["Worker Start", "Planner", "Capability Selection"]
    assert "Tool Invocation" in stages
    assert "Tool Resolution" in stages
    assert "Workflow Execution" in stages
    assert stages[-2:] == ["Final Response", "Worker Finish"]
    assert trace.total_duration_ms >= 0.0
    assert "task_plan" in trace.metadata
    assert "execution_graph" in trace.metadata
    assert "checkpoint_placeholders" in trace.metadata
    assert "graph_runtime" in trace.metadata
    assert "retries" in trace.metadata
    assert "queue_duration_ms" in trace.metadata
    assert "execution_duration_ms" in trace.metadata
    assert "node_status" in trace.metadata
    assert "checkpoint_state" in trace.metadata
    assert isinstance(trace.metadata["execution_graph"].get("nodes"), list)
    assert isinstance(trace.metadata["execution_graph"].get("edges"), list)
    assert isinstance(trace.metadata["graph_runtime"].get("retries"), dict)
    assert isinstance(
        trace.metadata["checkpoint_placeholders"].get("planning_checkpoint"),
        dict,
    )
    assert "inferred_capabilities" in trace.metadata
    assert "estimated_cost" in trace.metadata
    assert "complexity" in trace.metadata
    assert trace.metadata["execution_state"] == "completed"


def test_universal_worker_uses_highest_priority_for_same_capability() -> None:
    capability_registry = CapabilityRegistry()
    execution_recorder = ExecutionRecorder()
    capability_registry.register_tool(
        ToolMetadata(
            name="MemoryLow",
            description="Memory low priority",
            capabilities=["memory"],
            priority=10,
        )
    )
    capability_registry.register_tool(
        ToolMetadata(
            name="MemoryHigh",
            description="Memory high priority",
            capabilities=["memory"],
            priority=50,
        )
    )
    worker = UniversalWorker(
        planner=PlannerAgent(),
        workflow_engine=WorkflowEngine(
            registry=WorkflowRegistry(),
            executor=WorkflowExecutor(),
            queue=InMemoryWorkflowQueue(),
        ),
        tool_router=ToolRouter(),
        agent=DummyAgent(response="worker response"),
        capability_registry=capability_registry,
        execution_recorder=execution_recorder,
    )

    context = _context()
    context.memory_context = [{"k": "v"}]

    _ = worker.execute(context)

    assert context.metadata["selected_tool_metadata"] == ["MemoryHigh"]
