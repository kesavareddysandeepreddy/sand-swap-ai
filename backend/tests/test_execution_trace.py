from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlan
from backend.agents.planner import PlannerAgent
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.execution.recorder import ExecutionRecorder
from backend.execution.tracker import ExecutionTracker
from backend.tools.capability_registry import CapabilityRegistry
from backend.tools.tool_metadata import ToolMetadata
from backend.workers.universal_worker import UniversalWorker
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry


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
    conversation = Conversation(user_id="u1", id="u1:trace")
    return AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt="hello",
        prompt="rendered prompt",
        system_prompt="system prompt",
        model="model-a",
        metadata={"request_id": "req-1"},
    )


def test_trace_creation_and_step_lifecycle() -> None:
    recorder = ExecutionRecorder()
    trace = recorder.create_trace(worker_name="universal_worker", request_id="req-1")

    step = trace.add_step("Planner")
    trace.complete_step(step.id)
    trace.finish()

    assert trace.worker_name == "universal_worker"
    assert trace.request_id == "req-1"
    assert len(trace.steps) == 1
    assert trace.steps[0].status == "completed"
    assert trace.steps[0].duration_ms >= 0.0
    assert trace.total_duration_ms >= 0.0


def test_trace_failed_step() -> None:
    recorder = ExecutionRecorder()
    trace = recorder.create_trace(worker_name="universal_worker", request_id="req-1")

    step = trace.add_step("Workflow Execution")
    trace.fail_step(step.id, metadata={"reason": "boom"})

    assert trace.steps[0].status == "failed"
    assert trace.steps[0].metadata["reason"] == "boom"
    assert trace.steps[0].duration_ms >= 0.0


def test_recorder_lookup_recent_and_clear() -> None:
    recorder = ExecutionRecorder()
    t1 = recorder.create_trace(worker_name="w1", request_id="r1")
    t2 = recorder.create_trace(worker_name="w2", request_id="r2")

    assert recorder.get_trace(t1.trace_id) is t1
    assert [item.trace_id for item in recorder.list_recent(2)] == [
        t2.trace_id,
        t1.trace_id,
    ]

    recorder.clear()

    assert recorder.get_trace(t1.trace_id) is None
    assert recorder.list_recent(5) == []


def test_tracker_context_manager_records_completion() -> None:
    recorder = ExecutionRecorder()
    trace = recorder.create_trace(worker_name="w", request_id="r")
    tracker = ExecutionTracker(trace)

    with tracker.step("Planner"):
        value = 1 + 1

    assert value == 2
    assert trace.steps[0].stage == "Planner"
    assert trace.steps[0].status == "completed"
    assert trace.steps[0].duration_ms >= 0.0


def test_tracker_context_manager_records_failure() -> None:
    recorder = ExecutionRecorder()
    trace = recorder.create_trace(worker_name="w", request_id="r")
    tracker = ExecutionTracker(trace)

    try:
        with tracker.step("Workflow Execution"):
            raise RuntimeError("fail")
    except RuntimeError:
        pass

    assert trace.steps[0].status == "failed"
    assert trace.steps[0].metadata["exception_type"] == "RuntimeError"


def test_universal_worker_produces_execution_trace() -> None:
    capability_registry = CapabilityRegistry()
    capability_registry.register_tool(
        ToolMetadata(
            name="Memory",
            description="memory",
            capabilities=["memory"],
            priority=10,
        )
    )
    recorder = ExecutionRecorder()
    worker = UniversalWorker(
        planner=PlannerAgent(),
        workflow_engine=WorkflowEngine(
            registry=WorkflowRegistry(),
            executor=WorkflowExecutor(),
            queue=InMemoryWorkflowQueue(),
        ),
        tool_router=ToolRouter(),
        agent=DummyAgent(response="ok"),
        capability_registry=capability_registry,
        execution_recorder=recorder,
    )

    context = _context()
    context.memory_context = [{"k": "v"}]

    response = worker.execute(context)

    assert response == "ok"
    trace_id = context.metadata.get("execution_trace_id")
    assert isinstance(trace_id, str)
    trace = recorder.get_trace(trace_id)
    assert trace is not None
    assert trace.worker_name == "universal_worker"
    assert trace.request_id == "req-1"
    stages = [step.stage for step in trace.steps]
    assert stages[:3] == ["Worker Start", "Planner", "Capability Selection"]
    assert "Tool Invocation" in stages
    assert "Tool Resolution" in stages
    assert "Workflow Execution" in stages
    assert stages[-2:] == ["Final Response", "Worker Finish"]
    assert trace.total_duration_ms >= 0.0
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
    assert isinstance(trace.metadata["graph_runtime"].get("node_status"), dict)
    assert isinstance(
        trace.metadata["checkpoint_placeholders"].get("planning_checkpoint"),
        dict,
    )
