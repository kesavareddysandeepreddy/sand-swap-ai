from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-memory-pipeline.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-memory-rag"))
    monkeypatch.setenv(
        "ENTERPRISE_DB_PATH", str(tmp_path / "chat-memory-enterprise.db")
    )
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")
    with TestClient(app) as client:
        yield client


def _auth_headers(client: TestClient, user_id: str, email: str) -> dict[str, str]:
    user_service = client.app.state.container.resolve("user_service")
    existing = user_service.get_user_by_email(email)
    if existing is None:
        user_service.create_user(
            user_id=user_id,
            email=email,
            display_name=user_id,
        )
    else:
        user_id = existing.id
    token_service = client.app.state.container.resolve("token_service")
    token = token_service.create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


def _set_extractor_fallback_only(client: TestClient) -> None:
    extractor = client.app.state.container.resolve("memory_extractor")

    class EmptyExtractorClient:
        def generate(self, **kwargs: object):
            _ = kwargs
            return []

    extractor.client = EmptyExtractorClient()


def test_chat_message_creates_memory_visible_in_memory_api(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(runtime_client, "mem-user", "mem-user@example.com")
    _set_extractor_fallback_only(runtime_client)

    session = runtime_client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    workspace_id = session.json()["workspace_id"]
    project_id = session.json()["project_id"]

    chat_service = runtime_client.app.state.container.resolve("chat_service")

    asyncio.run(
        chat_service._extract_memories_after_response(
            "mem-user",
            "My name is Sandeep. I work as a Cloud Architect.",
            workspace_id=workspace_id,
            project_id=project_id,
        )
    )

    memories = runtime_client.get("/memory", headers=headers)
    assert memories.status_code == 200
    keys = {item["key"] for item in memories.json()["items"]}
    assert "name" in keys
    assert "job_title" in keys
    name_item = next(item for item in memories.json()["items"] if item["key"] == "name")
    assert name_item["value"] == "sandeep"


def test_chat_route_persists_name_memory_visible_in_memory_tab_source(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(runtime_client, "mem-user-route", "mem-route@example.com")
    _set_extractor_fallback_only(runtime_client)

    response = runtime_client.post(
        "/chat",
        headers=headers,
        json={
            "message": "My name is Sandeep.",
        },
    )
    assert response.status_code == 200

    import time

    for _ in range(20):
        memories = runtime_client.get("/memory", headers=headers)
        assert memories.status_code == 200
        items = memories.json()["items"]
        if any(item["key"] == "name" and item["value"] == "sandeep" for item in items):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("Expected 'name=sandeep' memory to be persisted via /chat")


def test_chat_context_retrieves_memory_for_question(runtime_client: TestClient) -> None:
    headers = _auth_headers(runtime_client, "mem-user-2", "mem-user-2@example.com")
    _set_extractor_fallback_only(runtime_client)

    chat_service = runtime_client.app.state.container.resolve("chat_service")

    asyncio.run(
        chat_service._extract_memories_after_response(
            "mem-user-2",
            "My name is Sandeep.",
            workspace_id="default",
            project_id="default",
        )
    )

    response = runtime_client.post(
        "/chat",
        headers=headers,
        json={
            "message": "What is my name?",
        },
    )
    assert response.status_code == 200


def test_memories_remain_isolated_by_project(runtime_client: TestClient) -> None:
    headers = _auth_headers(runtime_client, "mem-user-3", "mem-user-3@example.com")
    _set_extractor_fallback_only(runtime_client)

    primary = runtime_client.get("/auth/session", headers=headers)
    assert primary.status_code == 200
    workspace_id = primary.json()["workspace_id"]
    primary_project_id = primary.json()["project_id"]

    created = runtime_client.post(
        "/auth/projects",
        json={"name": "Secondary Project", "set_active": False},
        headers=headers,
    )
    assert created.status_code == 200
    secondary_project_id = created.json()["id"]

    chat_service = runtime_client.app.state.container.resolve("chat_service")

    asyncio.run(
        chat_service._extract_memories_after_response(
            "mem-user-3",
            "My name is Sandeep.",
            workspace_id=workspace_id,
            project_id=primary_project_id,
        )
    )

    switched = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": secondary_project_id},
        headers=headers,
    )
    assert switched.status_code == 200

    secondary_memories = runtime_client.get("/memory", headers=headers)
    assert secondary_memories.status_code == 200
    assert secondary_memories.json()["total"] == 0

    runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": primary_project_id},
        headers=headers,
    )
    primary_memories = runtime_client.get("/memory", headers=headers)
    assert primary_memories.status_code == 200
    assert any(item["key"] == "name" for item in primary_memories.json()["items"])
