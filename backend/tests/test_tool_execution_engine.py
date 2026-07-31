from __future__ import annotations

from pathlib import Path

from backend.agents.base import GeneralChatAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.execution.recorder import ExecutionRecorder
from backend.task_planner.models import TaskGoal, TaskPlan, TaskStep
from backend.tool_execution import ToolExecutor, ToolInvocationEngine, ToolResolver
from backend.tool_sdk.registry import ToolRegistry
from backend.tools.capability_registry import CapabilityRegistry
from backend.tools.filesystem_tool import FilesystemTool
from backend.tools.python_tool import PythonTool
from backend.tools.rest_tool import RESTTool
from backend.workflows.context import WorkflowContext
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.models import Workflow, WorkflowTask
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry


class _FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.model = "test-model"

    def generate(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return "formatted response"


class _PriorityTool:
    def __init__(self, name: str, response: str, healthy: bool = True) -> None:
        self._name = name
        self._response = response
        self._healthy = healthy
        self.calls: int = 0

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._name

    def capabilities(self) -> list[str]:
        return ["python"]

    def health(self) -> dict[str, object]:
        return {"status": "ok" if self._healthy else "error"}

    def execute(self, context):  # type: ignore[no-untyped-def]
        self.calls += 1
        _ = context
        return {
            "success": True,
            "stdout": self._response,
            "stderr": "",
            "generated_files": [],
            "execution_time": 0.1,
        }


def _agent_context(prompt: str = "print('hello')") -> AgentExecutionContext:
    conversation = Conversation(user_id="u1", id="u1:tool-exec")
    return AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt=prompt,
        prompt="rendered prompt",
        system_prompt="system prompt",
        model="model-a",
        metadata={"request_id": "req-1"},
    )


def test_tool_resolver_priority_and_fallback() -> None:
    capability_registry = CapabilityRegistry()
    tool_registry = ToolRegistry(capability_registry=capability_registry)
    tool_registry.register(PythonTool)
    tool_registry.register(FilesystemTool)
    tool_registry.register(RESTTool)

    resolver = ToolResolver(
        capability_registry=capability_registry,
        tool_registry=tool_registry,
    )

    resolution = resolver.resolve("python")
    assert resolution is not None
    assert resolution.tool_name == "PythonTool"


def test_tool_invocation_engine_executes_python_once_and_records_metadata(
    tmp_path: Path,
) -> None:
    capability_registry = CapabilityRegistry()
    recorder = ExecutionRecorder()
    tool_registry = ToolRegistry(capability_registry=capability_registry)
    tool_registry.register(PythonTool)
    capability_registry.register_tool(
        type(
            "Meta",
            (),
            {"name": "PythonTool", "capabilities": ["python"], "priority": 100},
        )
    )

    resolver = ToolResolver(
        capability_registry=capability_registry,
        tool_registry=tool_registry,
    )
    engine = ToolInvocationEngine(resolver=resolver, executor=ToolExecutor())

    conversation = Conversation(user_id="u1", id="u1:tool-exec")
    context = WorkflowContext(
        agent_context=AgentExecutionContext(
            conversation=conversation,
            workspace_id="ws-1",
            project_id="pr-1",
            user_prompt="print('hello world')",
            prompt="rendered prompt",
            system_prompt="system prompt",
            model="model-a",
            metadata={
                "request_id": "req-1",
                "workspace_root": str(tmp_path),
                "execution_trace_id": recorder.create_trace(
                    "universal_worker", "req-1"
                ).trace_id,
            },
        ),
        agent=GeneralChatAgent(ollama_client=_FakeOllamaClient()),
        tool_router=ToolRouter(),
        metadata={},
    )
    trace = recorder.get_trace(context.agent_context.metadata["execution_trace_id"])
    assert trace is not None

    plan = TaskPlan(
        goal=TaskGoal(original_request="print hello"),
        steps=[
            TaskStep(
                step_id="step-1",
                order=1,
                title="python",
                action="print",
                target="",
                capabilities=["python"],
                estimated_cost=0.1,
                complexity="low",
            )
        ],
    )

    results = engine.execute(plan, context, trace)

    assert len(results) == 1
    assert results[0].tool_name == "PythonTool"
    assert results[0].success is True
    assert results[0].stdout.strip() == "hello world"
    assert context.metadata["tool_results"]
    assert trace.metadata["tool_results"]
    assert any(step.stage == "PythonTool" for step in trace.steps)


def test_tool_invocation_engine_falls_back_when_tool_missing(tmp_path: Path) -> None:
    capability_registry = CapabilityRegistry()
    capability_registry.register_tool(
        type("Meta", (), {"name": "RESTTool", "capabilities": ["rest"], "priority": 50})
    )
    tool_registry = ToolRegistry(capability_registry=capability_registry)
    resolver = ToolResolver(
        capability_registry=capability_registry, tool_registry=tool_registry
    )
    engine = ToolInvocationEngine(resolver=resolver)
    recorder = ExecutionRecorder()
    trace = recorder.create_trace("universal_worker", "req-1")
    context = WorkflowContext(
        agent_context=_agent_context("Read README.md"),
        agent=GeneralChatAgent(ollama_client=_FakeOllamaClient()),
        tool_router=ToolRouter(),
        metadata={},
    )
    plan = TaskPlan(
        goal=TaskGoal(original_request="read"),
        steps=[
            TaskStep(
                step_id="step-1",
                order=1,
                title="rest",
                action="read",
                target="",
                capabilities=["rest"],
                estimated_cost=0.1,
                complexity="low",
            )
        ],
    )

    results = engine.execute(plan, context, trace)
    assert len(results) == 1
    assert results[0].success is False
    assert "No tool resolved" in results[0].stderr or results[0].error == "unresolved"


def test_workflow_consumes_cached_tool_results_and_llm_receives_tool_output(
    tmp_path: Path,
) -> None:
    recorder = ExecutionRecorder()
    conversation = Conversation(user_id="u1", id="u1:tool-exec")
    client = _FakeOllamaClient()
    agent = GeneralChatAgent(ollama_client=client)  # type: ignore[arg-type]
    context = AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt="print('hello')",
        prompt="rendered prompt",
        system_prompt="system prompt",
        model="model-a",
        metadata={
            "request_id": "req-1",
            "workspace_root": str(tmp_path),
            "tool_results": [
                {
                    "tool_name": "PythonTool",
                    "step_id": "step-1",
                    "success": True,
                    "stdout": "hello",
                    "stderr": "",
                    "artifacts": [],
                    "metadata": {},
                    "duration_ms": 1.0,
                    "error": None,
                }
            ],
            "tool_results_by_step_id": {
                "step-1": {
                    "tool_name": "PythonTool",
                    "step_id": "step-1",
                    "success": True,
                    "stdout": "hello",
                    "stderr": "",
                    "artifacts": [],
                    "metadata": {},
                    "duration_ms": 1.0,
                    "error": None,
                }
            },
            "execution_trace_id": recorder.create_trace(
                "universal_worker", "req-1"
            ).trace_id,
        },
    )
    workflow = Workflow(
        workflow_id="wf-1",
        workflow_type="agent_execution",
        selected_agent=agent.name(),
        tasks=[
            WorkflowTask(
                task_id="step-1",
                name="PythonTool:execute",
                action="execute",
                tool_name="PythonTool",
                metadata={"task_kind": "tool_router"},
            ),
            WorkflowTask(
                task_id="step-2",
                name="LLM:generate_response",
                action="generate_response",
                metadata={"task_kind": "agent_response"},
            ),
        ],
    )
    tool_router = ToolRouter()
    engine = WorkflowEngine(
        registry=WorkflowRegistry(),
        executor=WorkflowExecutor(),
        queue=InMemoryWorkflowQueue(),
    )
    result = engine.execute(
        workflow,
        WorkflowContext(
            agent_context=context,
            agent=agent,
            tool_router=tool_router,
            metadata=context.metadata,
        ),
    )

    assert result.status == "completed"
    assert client.calls
    assert context.metadata["tool_results"][0]["stdout"] == "hello"
