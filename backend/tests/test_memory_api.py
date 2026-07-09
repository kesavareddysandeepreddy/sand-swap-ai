from __future__ import annotations

from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.memory.core.memory_manager import MemoryManager


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory-api.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "memory-api-rag"))
    with TestClient(app) as client:
        yield client


def _manager(client: TestClient) -> MemoryManager:
    return client.app.state.container.resolve("memory_manager")


def test_memory_list_supports_filters_and_pagination(
    runtime_client: TestClient,
) -> None:
    manager = _manager(runtime_client)
    manager.remember(
        "user-1",
        "profile",
        "name",
        "Sandeep",
        category="identity",
        importance=0.9,
    )
    sleep(0.01)
    manager.remember(
        "user-1",
        "preference",
        "favorite_ide",
        "Cursor",
        category="preference",
        importance=0.8,
    )
    sleep(0.01)
    manager.remember(
        "user-1",
        "project",
        "project_name",
        "SandSwap AI",
        category="project",
        importance=0.7,
    )

    response = runtime_client.get(
        "/memory",
        params={
            "page": 1,
            "page_size": 2,
            "search": "favorite",
            "category": "preference",
            "min_importance": 0.5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["key"] == "favorite_ide"

    order_response = runtime_client.get("/memory", params={"page": 1, "page_size": 10})
    assert order_response.status_code == 200
    ordered_items = order_response.json()["items"]
    assert ordered_items[0]["key"] == "project_name"


def test_memory_get_patch_delete_single(runtime_client: TestClient) -> None:
    manager = _manager(runtime_client)
    record = manager.remember(
        "user-1",
        "goal",
        "learning_goal",
        "Kubernetes",
        category="goal",
        importance=0.85,
    )
    assert record is not None

    get_response = runtime_client.get(f"/memory/{record.id}")
    assert get_response.status_code == 200
    assert get_response.json()["value"] == "Kubernetes"

    patch_response = runtime_client.patch(
        f"/memory/{record.id}",
        json={
            "category": "skill",
            "key": "target_skill",
            "value": "Kubernetes",
            "importance": 0.95,
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["category"] == "skill"
    assert patched["key"] == "target_skill"
    assert patched["importance"] == 0.95

    delete_response = runtime_client.delete(f"/memory/{record.id}")
    assert delete_response.status_code == 204

    not_found = runtime_client.get(f"/memory/{record.id}")
    assert not_found.status_code == 404


def test_memory_delete_all(runtime_client: TestClient) -> None:
    manager = _manager(runtime_client)
    manager.remember("user-1", "profile", "name", "Sandeep", importance=0.9)
    manager.remember("user-1", "preference", "favorite_ide", "Cursor", importance=0.8)

    before = runtime_client.get("/memory")
    assert before.status_code == 200
    assert before.json()["total"] == 2

    delete_response = runtime_client.delete("/memory")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 2

    after = runtime_client.get("/memory")
    assert after.status_code == 200
    assert after.json()["total"] == 0
