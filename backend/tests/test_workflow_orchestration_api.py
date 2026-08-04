from __future__ import annotations

import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

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
) -> Generator[TestClient, None, None]:
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
        agent_service=cast(Any, _FakeAgentService()),
        llm_client=cast(Any, _FakeLLMClient()),
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


def test_workflow_versions_compare_restore_and_debugger_endpoints(
    orchestration_client: TestClient,
) -> None:
    created = orchestration_client.post(
        "/api/workflows",
        json={
            "name": "Versioned Workflow",
            "description": "Initial",
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

    updated = orchestration_client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "description": "Updated",
            "nodes": [
                {"id": "start", "node_type": "Start", "name": "Start"},
                {
                    "id": "agent-node",
                    "node_type": "Agent",
                    "name": "Planner v2",
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
    assert updated.status_code == 200

    versions = orchestration_client.get(f"/api/workflows/{workflow_id}/versions")
    assert versions.status_code == 200
    version_items = versions.json()
    assert len(version_items) >= 2

    compare = orchestration_client.get(
        f"/api/workflows/{workflow_id}/versions/compare?left_version=1&right_version=2"
    )
    assert compare.status_code == 200
    assert compare.json()["workflow_id"] == workflow_id
    assert isinstance(compare.json()["differences"], list)

    restore_version_id = str(version_items[0]["id"])
    restored = orchestration_client.post(
        f"/api/workflows/{workflow_id}/versions/{restore_version_id}/restore"
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == workflow_id

    executed = orchestration_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input_payload": {}, "wait_for_completion": True},
    )
    assert executed.status_code == 200
    run_id = executed.json()["run_id"]

    state = orchestration_client.get(f"/api/workflows/runs/{run_id}/state")
    assert state.status_code == 200
    assert state.json()["id"] == run_id

    debugger_payload = orchestration_client.get(
        f"/api/workflows/runs/{run_id}/debugger"
    )
    assert debugger_payload.status_code == 200
    debugger_json = debugger_payload.json()
    assert debugger_json["run"]["id"] == run_id
    assert isinstance(debugger_json["timeline"], list)

    node_records = state.json()["node_records"]
    assert len(node_records) >= 1
    node_id = str(node_records[0]["node_id"])
    node_details = orchestration_client.get(
        f"/api/workflows/runs/{run_id}/nodes/{node_id}"
    )
    assert node_details.status_code == 200
    assert node_details.json()["node_id"] == node_id

    stream = orchestration_client.get(f"/api/workflows/runs/{run_id}/events")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "workflow_completed" in stream.text

    registry = orchestration_client.get(f"/api/workflows/runs/{run_id}/agent-registry")
    assert registry.status_code == 200
    assert registry.json()["run_id"] == run_id

    messages = orchestration_client.get(f"/api/workflows/runs/{run_id}/messages")
    assert messages.status_code == 200
    assert messages.json()["run_id"] == run_id
    assert isinstance(messages.json()["messages"], list)

    timeline = orchestration_client.get(f"/api/workflows/runs/{run_id}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["run_id"] == run_id
    assert isinstance(timeline.json()["timeline"], list)

    artifacts = orchestration_client.get(f"/api/workflows/runs/{run_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["run_id"] == run_id
    assert isinstance(artifacts.json()["artifacts"], list)

    supervisor = orchestration_client.get(f"/api/workflows/runs/{run_id}/supervisor")
    assert supervisor.status_code == 200
    assert supervisor.json()["run_id"] == run_id
    assert isinstance(supervisor.json()["supervisor"], dict)


def test_workflow_pause_and_resume_endpoints(
    orchestration_client: TestClient,
) -> None:
    created = orchestration_client.post(
        "/api/workflows",
        json={
            "name": "Pause Resume Workflow",
            "description": "Delay for pause",
            "enabled": True,
            "nodes": [
                {"id": "start", "node_type": "Start", "name": "Start"},
                {
                    "id": "delay",
                    "node_type": "Delay",
                    "name": "Wait",
                    "config": {"seconds": 2},
                },
                {"id": "end", "node_type": "End", "name": "Done"},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source_node_id": "start",
                    "target_node_id": "delay",
                },
                {
                    "id": "e2",
                    "source_node_id": "delay",
                    "target_node_id": "end",
                },
            ],
        },
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    executed = orchestration_client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={"input_payload": {}, "wait_for_completion": False},
    )
    assert executed.status_code == 200
    run_id = executed.json()["run_id"]

    timeout_at = time.time() + 3
    run_status = "queued"
    while time.time() < timeout_at:
        run_response = orchestration_client.get(f"/api/workflows/runs/{run_id}")
        assert run_response.status_code == 200
        run_status = str(run_response.json()["status"])
        if run_status in {"running", "paused", "succeeded", "failed", "canceled"}:
            break
        time.sleep(0.05)

    paused = orchestration_client.post(f"/api/workflows/runs/{run_id}/pause")
    assert paused.status_code in {200, 422}

    if paused.status_code == 200:
        assert paused.json()["status"] == "paused"
        resumed = orchestration_client.post(f"/api/workflows/runs/{run_id}/resume")
        assert resumed.status_code == 200
        assert resumed.json()["status"] in {"queued", "running", "succeeded", "paused"}
    else:
        assert run_status in {"succeeded", "failed", "canceled", "waiting_approval"}

    canceled = orchestration_client.post(f"/api/workflows/runs/{run_id}/cancel")
    assert canceled.status_code == 200

    retried = orchestration_client.post(
        f"/api/workflows/runs/{run_id}/retry",
        json={"policy": "immediate", "task_id": ""},
    )
    if canceled.json()["status"] in {"failed", "canceled"}:
        assert retried.status_code == 200
        assert retried.json()["id"] == run_id
    else:
        assert retried.status_code == 422
