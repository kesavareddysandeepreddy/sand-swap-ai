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


def _auth_headers(client: TestClient, user_id: str = "user-1") -> dict[str, str]:
    token_service = client.app.state.container.resolve("token_service")
    token = token_service.create_access_token(user_id, f"{user_id}@example.com")
    return {"Authorization": f"Bearer {token}"}


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
        headers=_auth_headers(runtime_client, "user-1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["key"] == "favorite_ide"

    order_response = runtime_client.get(
        "/memory",
        params={"page": 1, "page_size": 10},
        headers=_auth_headers(runtime_client, "user-1"),
    )
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

    headers = _auth_headers(runtime_client, "user-1")

    get_response = runtime_client.get(f"/memory/{record.id}", headers=headers)
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
        headers=headers,
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["category"] == "skill"
    assert patched["key"] == "target_skill"
    assert patched["importance"] == 0.95

    delete_response = runtime_client.delete(f"/memory/{record.id}", headers=headers)
    assert delete_response.status_code == 204

    not_found = runtime_client.get(f"/memory/{record.id}", headers=headers)
    assert not_found.status_code == 404


def test_memory_delete_all(runtime_client: TestClient) -> None:
    manager = _manager(runtime_client)
    manager.remember("user-1", "profile", "name", "Sandeep", importance=0.9)
    manager.remember("user-1", "preference", "favorite_ide", "Cursor", importance=0.8)

    headers = _auth_headers(runtime_client, "user-1")

    before = runtime_client.get("/memory", headers=headers)
    assert before.status_code == 200
    assert before.json()["total"] == 2

    delete_response = runtime_client.delete("/memory", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 2

    after = runtime_client.get("/memory", headers=headers)
    assert after.status_code == 200
    assert after.json()["total"] == 0


def test_memory_list_is_isolated_by_authenticated_owner(
    runtime_client: TestClient,
) -> None:
    manager = _manager(runtime_client)
    own = manager.remember("user-a", "profile", "name", "Alice", importance=0.9)
    other = manager.remember("user-b", "profile", "name", "Bob", importance=0.9)
    assert own is not None
    assert other is not None

    token_service = runtime_client.app.state.container.resolve("token_service")
    token = token_service.create_access_token("user-a", "alice@example.com")

    response = runtime_client.get(
        "/memory",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == "user-a"


def test_memory_get_denies_cross_user_access(
    runtime_client: TestClient,
) -> None:
    manager = _manager(runtime_client)
    mine = manager.remember("user-a", "goal", "target", "A", importance=0.9)
    other = manager.remember("user-b", "goal", "target", "B", importance=0.9)
    assert mine is not None
    assert other is not None

    token_service = runtime_client.app.state.container.resolve("token_service")
    token = token_service.create_access_token("user-a", "alice@example.com")

    own_response = runtime_client.get(
        f"/memory/{mine.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert own_response.status_code == 200

    cross_response = runtime_client.get(
        f"/memory/{other.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cross_response.status_code == 404


def test_authenticated_user_cannot_access_anonymous_memory(
    runtime_client: TestClient,
) -> None:
    manager = _manager(runtime_client)
    anonymous = manager.remember("anonymous", "fact", "note", "legacy", importance=0.9)
    assert anonymous is not None

    token_service = runtime_client.app.state.container.resolve("token_service")
    token = token_service.create_access_token("user-a", "alice@example.com")

    response = runtime_client.get(
        f"/memory/{anonymous.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_anonymous_user_cannot_access_authenticated_memory(
    runtime_client: TestClient,
) -> None:
    manager = _manager(runtime_client)
    authenticated = manager.remember(
        "user-a", "fact", "note", "private", importance=0.9
    )
    assert authenticated is not None

    response = runtime_client.get(f"/memory/{authenticated.id}")
    assert response.status_code == 404
