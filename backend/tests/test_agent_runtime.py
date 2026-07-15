from __future__ import annotations

from backend.agents.base import BaseAgent, GeneralChatAgent
from backend.agents.context import AgentExecutionContext
from backend.agents.execution import AgentExecutor
from backend.agents.models import AgentExecutionPlan, AgentExecutionPlanStep
from backend.agents.planner import PlannerAgent
from backend.agents.registry import AgentRegistry
from backend.agents.runtime import AgentRuntime
from backend.agents.tool_router import ToolRouter
from backend.chat.domain.conversation import Conversation
from backend.mcp.models import MCPToolCallResult
from backend.workflows.models import WorkflowTask


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.model = "test-model"

    def generate(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return "runtime response"


class FakeMCPClient:
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


class DummyAgent(BaseAgent):
    def name(self) -> str:
        return "dummy"

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
        return "dummy response"

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


def _context() -> AgentExecutionContext:
    conversation = Conversation(user_id="u1", id="u1:conv-1")
    return AgentExecutionContext(
        conversation=conversation,
        workspace_id="ws-1",
        project_id="pr-1",
        knowledge_object_ids=["k1"],
        knowledge_context="knowledge block",
        memory_context=[{"key": "name", "value": "Ada"}],
        rag_context=[{"chunk": "doc"}],
        vision_context="vision block",
        user_prompt="hello",
        prompt="rendered prompt",
        system_prompt="system prompt",
        model="model-a",
        metadata={"temperature": 0.2},
    )


def test_execution_context_fields() -> None:
    context = _context()
    assert context.workspace_id == "ws-1"
    assert context.project_id == "pr-1"
    assert context.knowledge_object_ids == ["k1"]
    assert context.user_prompt == "hello"


def test_planner_generates_plan() -> None:
    planner = PlannerAgent()
    plan = planner.plan(_context(), selected_agent="general_chat_agent")

    assert plan.selected_agent == "general_chat_agent"
    assert plan.workflow_type == "agent_execution"
    assert any(task.tool_name == "KnowledgeService" for task in plan.tasks)
    assert any(task.tool_name == "Memory" for task in plan.tasks)
    assert any(task.tool_name == "RAG" for task in plan.tasks)
    assert any(
        task.metadata.get("task_kind") == "agent_response" for task in plan.tasks
    )


def test_registry_register_discover_lookup_health() -> None:
    registry = AgentRegistry()
    agent = DummyAgent()
    registry.register(agent)

    discovered = registry.discover()
    assert [item.name() for item in discovered] == ["dummy"]
    assert registry.lookup("dummy") is agent
    assert registry.health()["dummy"]["status"] == "ok"


def test_tool_router_selects_registered_tools() -> None:
    router = ToolRouter()
    router.register_tool("KnowledgeService", object())
    router.register_tool("Memory", object())

    plan = AgentExecutionPlan(
        selected_agent="dummy",
        steps=[
            AgentExecutionPlanStep(tool="KnowledgeService", action="inspect"),
            AgentExecutionPlanStep(tool="Memory", action="retrieve"),
            AgentExecutionPlanStep(tool="RAG", action="retrieve"),
        ],
    )
    selected = router.select_tools(_context(), plan)

    assert sorted(selected.keys()) == ["KnowledgeService", "Memory"]


def test_tool_router_invokes_workflow_task_via_lookup() -> None:
    router = ToolRouter()
    router.register_tool("KnowledgeService", object())

    result = router.invoke_task(
        task=WorkflowTask(
            task_id="t1",
            name="KnowledgeService:inspect",
            action="inspect",
            tool_name="KnowledgeService",
        ),
        context=_context(),
    )

    assert result["status"] == "completed"
    assert result["tool"] == "KnowledgeService"


def test_general_chat_agent_preserves_llm_behavior() -> None:
    client = FakeOllamaClient()
    agent = GeneralChatAgent(ollama_client=client)  # type: ignore[arg-type]

    result = agent.execute(_context())

    assert result == "runtime response"
    assert client.calls
    assert client.calls[-1]["prompt"] == "rendered prompt"
    assert client.calls[-1]["system"] == "system prompt"


def test_runtime_selects_agent_plans_and_executes() -> None:
    client = FakeOllamaClient()
    general_agent = GeneralChatAgent(ollama_client=client)  # type: ignore[arg-type]
    registry = AgentRegistry()
    registry.register(general_agent)

    runtime = AgentRuntime(
        registry=registry,
        planner=PlannerAgent(),
        tool_router=ToolRouter(),
        executor=AgentExecutor(),
    )

    result = runtime.execute(_context())

    assert result.agent_name == "general_chat_agent"
    assert result.response_text == "runtime response"
    assert result.plan.selected_agent == "general_chat_agent"
    assert result.metadata["workflow_status"] == "completed"


def test_planner_adds_mcp_task_from_context_metadata() -> None:
    planner = PlannerAgent()
    context = _context()
    context.metadata["mcp_tools"] = [{"server": "filesystem", "tool": "read_file"}]

    workflow = planner.plan(context, selected_agent="general_chat_agent")

    assert workflow.tasks[0].tool_name == "MCP"
    assert workflow.tasks[0].mcp_server == "filesystem"
    assert workflow.tasks[0].mcp_tool == "read_file"


def test_runtime_executes_mcp_tool_when_planned() -> None:
    client = FakeOllamaClient()
    mcp = FakeMCPClient()
    general_agent = GeneralChatAgent(ollama_client=client)  # type: ignore[arg-type]

    registry = AgentRegistry()
    registry.register(general_agent)

    router = ToolRouter()
    router.register_tool("MCP", mcp)

    runtime = AgentRuntime(
        registry=registry,
        planner=PlannerAgent(),
        tool_router=router,
        executor=AgentExecutor(),
    )

    context = _context()
    context.metadata["mcp_tools"] = [{"server": "filesystem", "tool": "read_file"}]

    result = runtime.execute(context)

    assert result.metadata["workflow_status"] == "completed"
    assert mcp.calls == [("filesystem", "read_file", {})]
