from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agent_orchestration.application.workflow_service import WorkflowService
from backend.agent_orchestration.executor.workflow_executor import (
    WorkflowExecutionEngine,
)
from backend.agent_orchestration.infrastructure.sqlite_workflow_repository import (
    SQLiteWorkflowRepository,
)
from backend.agent_orchestration.planner.validator import WorkflowValidator
from backend.agent_orchestration.scheduler.background_scheduler import (
    BackgroundWorkflowScheduler,
)
from backend.api.dependencies import get_workflow_service
from backend.api.main import app


class _FakeAgent:
    def __init__(self) -> None:
        self.id = "agent-1"
        self.name = "Planner"
        self.goal = "Generate structured plan"
        self.instructions = "Plan concisely"
        self.system_prompt = "Return JSON"
        self.model = ""
        self.temperature = 0.0


class _FakeAgentService:
    def __init__(self) -> None:
        self._agent = _FakeAgent()

    def list_agents(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[_FakeAgent]:
        _ = (owner_id, workspace_id, project_id)
        return [self._agent]

    def get_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> _FakeAgent | None:
        _ = (owner_id, workspace_id, project_id)
        if agent_id == self._agent.id:
            return self._agent
        return None


class _FakeLLMClient:
    def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None,
        temperature: float,
        format_json: bool,
    ) -> dict[str, object]:
        _ = (prompt, system, model, temperature, format_json)
        return {
            "result": "ok",
            "reasoning": "planned",
            "tool_outputs": [],
        }


@pytest.fixture
def orchestration_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "enterprise.db"))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    repository = SQLiteWorkflowRepository(db_path=str(tmp_path / "orchestration.db"))
    service = WorkflowService(
        repository=repository,
        validator=WorkflowValidator(),
        engine=WorkflowExecutionEngine(),
        scheduler=BackgroundWorkflowScheduler(max_workers=1),
        agent_service=_FakeAgentService(),
        llm_client=_FakeLLMClient(),
    )

    app.dependency_overrides[get_workflow_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_workflow_crud_validate_execute_and_list_runs(
    orchestration_client: TestClient,
) -> None:
    created = orchestration_client.post(
        "/api/workflows",
        json={
            "name": "Plan Workflow",
            "description": "Simple orchestration",
            "enabled": True,
            "nodes": [
                {"id": "start", "node_type": "Start", "name": "Start"},
                {
                    "id": "agent-node",
                    "node_type": "Agent",
                    "name": "Planner",
                    "agent_id": "agent-1",
                },
                {"id": "end", "node_type": "End", "name": "Done"},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source_node_id": "start",
                    "target_node_id": "agent-node",
                },
                {
                    "id": "e2",
                    "source_node_id": "agent-node",
                    "target_node_id": "end",
                },
            ],
        },
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    listed = orchestration_client.get("/api/workflows")
    assert listed.status_code == 200
    assert any(item["id"] == workflow_id for item in listed.json())

    validated = orchestration_client.post(f"/api/workflows/{workflow_id}/validate")
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    executed = orchestration_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input_payload": {"topic": "release"}, "wait_for_completion": True},
    )
    assert executed.status_code == 200
    run_id = executed.json()["run_id"]
    assert executed.json()["status"] == "succeeded"

    run = orchestration_client.get(f"/api/workflows/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["workflow_id"] == workflow_id
    assert run.json()["status"] == "succeeded"

    runs = orchestration_client.get(f"/api/workflows/{workflow_id}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) >= 1


def test_workflow_human_approval_reject_action(
    orchestration_client: TestClient,
) -> None:
    created = orchestration_client.post(
        "/api/workflows",
        json={
            "name": "Approval Workflow",
            "description": "Requires approval",
            "enabled": True,
            "nodes": [
                {"id": "start", "node_type": "Start", "name": "Start"},
                {
                    "id": "approval",
                    "node_type": "Human Approval",
                    "name": "Approve",
                    "config": {"auto_approve": False},
                },
                {"id": "end", "node_type": "End", "name": "Done"},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source_node_id": "start",
                    "target_node_id": "approval",
                },
                {
                    "id": "e2",
                    "source_node_id": "approval",
                    "target_node_id": "end",
                },
            ],
        },
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    executed = orchestration_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input_payload": {}, "wait_for_completion": True},
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "waiting_approval"
    run_id = executed.json()["run_id"]

    rejected = orchestration_client.post(
        f"/api/workflows/runs/{run_id}/actions",
        json={"action": "reject", "edited_input": {}},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "canceled"
