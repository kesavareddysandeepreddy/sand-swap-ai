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
    monkeypatch.setenv(
        "MEMORY_DB_PATH", str(tmp_path / "chat-conversation-restore-memory.db")
    )
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-conversation-restore-rag"))
    monkeypatch.setenv(
        "ENTERPRISE_DB_PATH",
        str(tmp_path / "chat-conversation-restore-enterprise.db"),
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


def _set_ollama_echo(client: TestClient) -> None:
    chat_service = client.app.state.container.resolve("chat_service")

    def _generate(**kwargs: object) -> str:
        prompt = str(kwargs.get("prompt", ""))
        return f"echo:{prompt[:12]}"

    chat_service.ollama_client.generate = _generate


def _chat(
    client: TestClient,
    headers: dict[str, str],
    message: str,
    conversation_id: str | None = None,
) -> str:
    payload: dict[str, str] = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/chat", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()["conversation_id"]


def _list_conversations(
    client: TestClient,
    headers: dict[str, str],
) -> list[dict[str, object]]:
    response = client.get("/chat/conversations", headers=headers)
    assert response.status_code == 200
    return response.json()["items"]


def test_conversation_survives_logout_login_and_new_session(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "restore-user",
        "restore-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    conversation_id = _chat(runtime_client, headers, "Hello from session one")
    _chat(runtime_client, headers, "Second turn", conversation_id=conversation_id)

    # Simulate reopening in a new browser/session by fetching conversations from API.
    listed = _list_conversations(runtime_client, headers)
    ids = [item["id"] for item in listed]
    assert conversation_id in ids

    restored = next(item for item in listed if item["id"] == conversation_id)
    assert len(restored["messages"]) >= 2


def test_conversations_are_scoped_to_active_project(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "project-scope-user",
        "project-scope-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    session = runtime_client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    project_a = session.json()["project_id"]

    created = runtime_client.post(
        "/auth/projects",
        json={"name": "Project B", "set_active": False},
        headers=headers,
    )
    assert created.status_code == 200
    project_b = created.json()["id"]

    conv_a = _chat(runtime_client, headers, "Project A conversation")
    assert conv_a

    switched_to_b = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": project_b},
        headers=headers,
    )
    assert switched_to_b.status_code == 200

    conv_b = _chat(runtime_client, headers, "Project B conversation")
    assert conv_b

    list_b = _list_conversations(runtime_client, headers)
    assert {item["id"] for item in list_b} == {conv_b}

    switched_to_a = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": project_a},
        headers=headers,
    )
    assert switched_to_a.status_code == 200

    list_a = _list_conversations(runtime_client, headers)
    assert {item["id"] for item in list_a} == {conv_a}


def test_conversations_are_isolated_between_users(
    runtime_client: TestClient,
) -> None:
    user_a = _auth_headers(runtime_client, "chat-user-a", "chat-a@example.com")
    user_b = _auth_headers(runtime_client, "chat-user-b", "chat-b@example.com")
    _set_ollama_echo(runtime_client)

    conv_a = _chat(runtime_client, user_a, "A secret conversation")
    conv_b = _chat(runtime_client, user_b, "B secret conversation")

    list_a = _list_conversations(runtime_client, user_a)
    list_b = _list_conversations(runtime_client, user_b)

    assert {item["id"] for item in list_a} == {conv_a}
    assert {item["id"] for item in list_b} == {conv_b}
