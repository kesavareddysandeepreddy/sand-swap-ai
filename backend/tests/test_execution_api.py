from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "execution-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "execution-rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "execution-enterprise.db"))
    with TestClient(app) as client:
        yield client


def _create_trace(client: TestClient) -> str:
    recorder = client.app.state.container.resolve("execution_recorder")
    trace = recorder.create_trace(worker_name="universal_worker", request_id="req-1")
    trace.metadata.update(
        {
            "task_plan": {"steps": []},
            "inferred_capabilities": ["workflow"],
            "estimated_cost": 0.42,
            "complexity": "low",
            "execution_state": "completed",
        }
    )
    step = trace.add_step("Planner", metadata={"phase": "planning"})
    trace.complete_step(step.id, metadata={"result": "ok"})
    trace.finish()
    return trace.trace_id


def test_recent_traces(runtime_client: TestClient) -> None:
    trace_id = _create_trace(runtime_client)

    response = runtime_client.get("/api/execution/recent")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert payload[0]["trace_id"] == trace_id
    assert payload[0]["worker_name"] == "universal_worker"


def test_trace_lookup(runtime_client: TestClient) -> None:
    trace_id = _create_trace(runtime_client)

    response = runtime_client.get(f"/api/execution/trace/{trace_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == trace_id
    assert payload["worker_name"] == "universal_worker"
    assert payload["request_id"] == "req-1"
    assert isinstance(payload["metadata"], dict)
    assert payload["metadata"]["task_plan"] == {"steps": []}
    assert payload["metadata"]["inferred_capabilities"] == ["workflow"]
    assert payload["metadata"]["estimated_cost"] == 0.42
    assert payload["metadata"]["complexity"] == "low"
    assert payload["metadata"]["execution_state"] == "completed"
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["stage"] == "Planner"
    assert payload["steps"][0]["status"] == "completed"
    assert payload["steps"][0]["metadata"]["phase"] == "planning"
    assert payload["steps"][0]["metadata"]["result"] == "ok"


def test_invalid_trace(runtime_client: TestClient) -> None:
    response = runtime_client.get("/api/execution/trace/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Execution trace not found"


def test_health_endpoint(runtime_client: TestClient) -> None:
    _ = _create_trace(runtime_client)

    response = runtime_client.get("/api/execution/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recorder_status"] == "ok"
    assert payload["traces"] >= 1


def test_chat_request_creates_trace_visible_in_execution_api(
    runtime_client: TestClient,
) -> None:
    response = runtime_client.post(
        "/chat",
        json={
            "user_id": "anon-session-1",
            "message": "hello execution trace",
        },
    )
    assert response.status_code == 200

    recent = runtime_client.get("/api/execution/recent")
    assert recent.status_code == 200
    payload = recent.json()
    assert payload

    trace_id = payload[0]["trace_id"]
    trace_response = runtime_client.get(f"/api/execution/trace/{trace_id}")
    assert trace_response.status_code == 200
    trace = trace_response.json()

    assert trace["worker_name"] == "universal_worker"
    assert isinstance(trace["metadata"], dict)
    assert "task_plan" in trace["metadata"]
    assert isinstance(trace["metadata"]["task_plan"], dict)
    assert "steps" in trace["metadata"]["task_plan"]
    assert "inferred_capabilities" in trace["metadata"]
    assert isinstance(trace["metadata"]["inferred_capabilities"], list)
    assert "estimated_cost" in trace["metadata"]
    assert isinstance(trace["metadata"]["estimated_cost"], float | int)
    assert "complexity" in trace["metadata"]
    assert trace["metadata"]["complexity"] in {"low", "medium", "high"}
    assert "execution_state" in trace["metadata"]
    assert trace["metadata"]["execution_state"] == "completed"
    assert "execution_graph" in trace["metadata"]
    assert isinstance(trace["metadata"]["execution_graph"], dict)
    assert "nodes" in trace["metadata"]["execution_graph"]
    assert isinstance(trace["metadata"]["execution_graph"]["nodes"], list)
    assert "edges" in trace["metadata"]["execution_graph"]
    assert isinstance(trace["metadata"]["execution_graph"]["edges"], list)
    assert "retries" in trace["metadata"]
    assert isinstance(trace["metadata"]["retries"], dict)
    assert "queue_duration_ms" in trace["metadata"]
    assert isinstance(trace["metadata"]["queue_duration_ms"], dict)
    assert "execution_duration_ms" in trace["metadata"]
    assert isinstance(trace["metadata"]["execution_duration_ms"], dict)
    assert "node_status" in trace["metadata"]
    assert isinstance(trace["metadata"]["node_status"], dict)
    assert "checkpoint_state" in trace["metadata"]
    assert isinstance(trace["metadata"]["checkpoint_state"], dict)
    assert "checkpoint_placeholders" in trace["metadata"]
    assert isinstance(trace["metadata"]["checkpoint_placeholders"], dict)
    stages = [step["stage"] for step in trace["steps"]]
    assert "Worker Start" in stages
    assert "Planner" in stages
    assert "Workflow Execution" in stages
    assert "Final Response" in stages
