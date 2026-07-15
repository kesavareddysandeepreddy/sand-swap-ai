from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlanStep
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.mcp.models import MCPToolCallResult
from backend.workflows.context import WorkflowContext
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.models import Workflow, WorkflowTask
from backend.workflows.planner import WorkflowPlanner
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry
from backend.workflows.task import Task


class DummyAgent(BaseAgent):
    def name(self) -> str:
        return "dummy"

    def description(self) -> str:
        return "dummy"

    def can_handle(self, context: AgentExecutionContext) -> bool:
        _ = context
        return True

    def plan(self, context: AgentExecutionContext):
        _ = context
        raise NotImplementedError

    def execute(self, context: AgentExecutionContext) -> str:
        _ = context
        return "workflow response"

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


class _RecordingTool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def execute_workflow_task(
        self, *, task: WorkflowTask, context: AgentExecutionContext
    ):
        self.calls.append((task.action, context.user_prompt))
        return {"ok": True}


class _RecordingMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object] | None = None,
    ):
        payload = dict(arguments or {})
        self.calls.append((server_name, tool_name, payload))
        return MCPToolCallResult(
            server_name=server_name,
            tool_name=tool_name,
            content={"ok": True},
            latency_ms=1.0,
            is_error=False,
            error=None,
        )


class _RetryTask(Task):
    def __init__(self, definition: WorkflowTask) -> None:
        super().__init__(definition)
        self._attempts = 0

    def execute(self, context: WorkflowContext) -> dict[str, object]:
        _ = context
        self._attempts += 1
        if self._attempts == 1:
            raise RuntimeError("transient")
        return {"status": "ok"}

    def rollback(self, context: WorkflowContext) -> dict[str, object]:
        _ = context
        return {"status": "noop"}

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


class _CancelTask(Task):
    def execute(self, context: WorkflowContext) -> dict[str, object]:
        context.cancel()
        return {"status": "cancelled"}

    def rollback(self, context: WorkflowContext) -> dict[str, object]:
        _ = context
        return {"status": "noop"}

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


def _context() -> WorkflowContext:
    conversation = Conversation(user_id="u1", id="u1:conv-wf")
    agent_context = AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        user_prompt="hello",
        prompt="prompt",
        system_prompt="system",
        model="m1",
    )
    return WorkflowContext(
        agent_context=agent_context,
        agent=DummyAgent(),
        tool_router=ToolRouter(),
    )


def test_queue_lifecycle() -> None:
    queue = InMemoryWorkflowQueue()
    workflow = Workflow(
        workflow_id="wf-1",
        workflow_type="test",
        selected_agent="dummy",
        tasks=[],
    )

    queue.enqueue(workflow)

    assert queue.size() == 1
    assert queue.peek() is workflow
    assert queue.dequeue() is workflow
    assert queue.is_empty() is True


def test_registry_register_and_create() -> None:
    registry = WorkflowRegistry()

    def factory() -> Workflow:
        return Workflow(
            workflow_id="wf-reg",
            workflow_type="registered",
            selected_agent="dummy",
            tasks=[],
        )

    registry.register("registered", factory)

    built = registry.create("registered")

    assert built.workflow_id == "wf-reg"
    assert registry.discover() == ["registered"]


def test_planner_converts_execution_steps_to_workflow() -> None:
    planner = WorkflowPlanner()
    workflow = planner.from_execution_plan(
        workflow_type="agent_execution",
        selected_agent="dummy",
        rationale="test rationale",
        steps=[
            AgentExecutionPlanStep(
                tool="KnowledgeService",
                action="inspect",
                reason="knowledge present",
            ),
            AgentExecutionPlanStep(
                tool="LLM",
                action="generate_response",
                reason="final answer",
            ),
        ],
        metadata={"x": 1},
    )

    assert workflow.workflow_type == "agent_execution"
    assert len(workflow.tasks) == 2
    assert workflow.tasks[0].tool_name == "KnowledgeService"
    assert workflow.tasks[1].metadata["task_kind"] == "agent_response"


def test_executor_runs_tasks_and_returns_response() -> None:
    context = _context()
    tool = _RecordingTool()
    context.tool_router.register_tool("KnowledgeService", tool)

    workflow = Workflow(
        workflow_id="wf-ok",
        workflow_type="agent_execution",
        selected_agent="dummy",
        tasks=[
            WorkflowTask(
                task_id="t1",
                name="KnowledgeService:inspect",
                tool_name="KnowledgeService",
                action="inspect",
                metadata={"task_kind": "tool_router"},
            ),
            WorkflowTask(
                task_id="t2",
                name="LLM:generate_response",
                action="generate_response",
                metadata={"task_kind": "agent_response"},
            ),
        ],
    )

    result = WorkflowExecutor().execute(workflow, context)

    assert result.status == "completed"
    assert result.response_text == "workflow response"
    assert len(result.task_results) == 2
    assert tool.calls == [("inspect", "hello")]


def test_executor_retries_transient_failure() -> None:
    context = _context()
    workflow = Workflow(
        workflow_id="wf-retry",
        workflow_type="agent_execution",
        selected_agent="dummy",
        tasks=[
            WorkflowTask(
                task_id="t1",
                name="retry-task",
                action="retry",
                max_retries=1,
            )
        ],
    )

    executor = WorkflowExecutor(task_factory=lambda definition: _RetryTask(definition))
    result = executor.execute(workflow, context)

    assert result.status == "completed"
    assert result.task_results[0].attempts == 2


def test_executor_cancellation_and_engine_execution() -> None:
    context = _context()
    workflow = Workflow(
        workflow_id="wf-cancel",
        workflow_type="agent_execution",
        selected_agent="dummy",
        tasks=[
            WorkflowTask(
                task_id="t1",
                name="cancel-task",
                action="cancel",
            ),
            WorkflowTask(
                task_id="t2",
                name="never-runs",
                action="later",
            ),
        ],
    )

    engine = WorkflowEngine(
        registry=WorkflowRegistry(),
        executor=WorkflowExecutor(
            task_factory=lambda definition: _CancelTask(definition)
        ),
        queue=InMemoryWorkflowQueue(),
    )
    result = engine.execute(workflow, context)

    assert result.status == "cancelled"
    assert len(result.task_results) == 1


def test_executor_runs_mcp_tool_task() -> None:
    context = _context()
    mcp_client = _RecordingMCPClient()
    context.tool_router.register_tool("MCP", mcp_client)

    workflow = Workflow(
        workflow_id="wf-mcp",
        workflow_type="agent_execution",
        selected_agent="dummy",
        tasks=[
            WorkflowTask(
                task_id="t1",
                name="MCP:filesystem.read_file",
                action="call_tool",
                tool_name="MCP",
                mcp_server="filesystem",
                mcp_tool="read_file",
                mcp_arguments={"path": "a.txt"},
                metadata={"task_kind": "tool_router"},
            ),
            WorkflowTask(
                task_id="t2",
                name="LLM:generate_response",
                action="generate_response",
                metadata={"task_kind": "agent_response"},
            ),
        ],
    )

    result = WorkflowExecutor().execute(workflow, context)

    assert result.status == "completed"
    assert mcp_client.calls == [("filesystem", "read_file", {"path": "a.txt"})]
