from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "persistent-memory-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "persistent-memory-rag"))
    monkeypatch.setenv(
        "ENTERPRISE_DB_PATH", str(tmp_path / "persistent-memory-enterprise.db")
    )
    monkeypatch.setenv(
        "CHAT_CONVERSATION_DB_PATH",
        str(tmp_path / "persistent-memory-conversations.db"),
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
    token_service = client.app.state.container.resolve("token_service")
    token = token_service.create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


class _DeterministicMemoryExtractor:
    def __init__(self, memory_manager: object) -> None:
        self._memory_manager = memory_manager

    def process(
        self,
        user_id: str,
        message: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[object]:
        saved: list[object] = []

        def remember(key: str, value: str, category: str) -> None:
            stored = self._memory_manager.remember(
                user_id=user_id,
                memory_type="fact",
                key=key,
                value=value,
                category=category,
                importance=0.95,
                confidence=0.95,
                project_id=project_id,
                metadata={"workspace_id": workspace_id},
            )
            if stored is not None:
                saved.append(stored)

        text = message.strip()

        name_match = re.search(r"my name is\s+(.+?)[.!?]?$", text, re.IGNORECASE)
        if name_match:
            remember("name", name_match.group(1).strip(), "identity")

        occupation_match = re.search(
            r"(?:i am a|i am an|i work as)\s+(.+?)[.!?]?$",
            text,
            re.IGNORECASE,
        )
        if occupation_match:
            remember("occupation", occupation_match.group(1).strip(), "work")

        language_match = re.search(r"i prefer\s+(.+?)[.!?]?$", text, re.IGNORECASE)
        if language_match:
            remember(
                "preferred_language", language_match.group(1).strip(), "preference"
            )

        return saved


class _DeterministicGenerator:
    @staticmethod
    def generate(*, prompt: str, **_: object) -> str:
        facts: dict[str, str] = {}
        for line in prompt.splitlines():
            if line.startswith("- ") and ":" in line:
                key, value = line[2:].split(":", maxsplit=1)
                facts[key.strip().lower()] = value.strip()

        question = ""
        for line in prompt.splitlines():
            if line.startswith("User question:"):
                question = line.split(":", maxsplit=1)[1].strip().lower()
                break

        if "what is my name" in question and "name" in facts:
            return f"Your name is {facts['name']}."

        if "what do i do" in question and "occupation" in facts:
            return f"You are a {facts['occupation']}."

        if "what language do i prefer" in question and "preferred_language" in facts:
            return f"You prefer {facts['preferred_language']}."

        return "I can help with that."


def _configure_chat_runtime(client: TestClient) -> None:
    chat_service = client.app.state.container.resolve("chat_service")
    chat_service.agent_runtime = None
    chat_service.ollama_client.generate = _DeterministicGenerator.generate
    chat_service.memory_extractor = _DeterministicMemoryExtractor(
        chat_service.memory_manager
    )


def _chat(
    client: TestClient,
    headers: dict[str, str],
    message: str,
    conversation_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, str] = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/chat", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()


def test_name_is_available_across_conversations(runtime_client: TestClient) -> None:
    _configure_chat_runtime(runtime_client)
    headers = _auth_headers(runtime_client, "memory-user", "memory-user@example.com")

    first = _chat(runtime_client, headers, "My name is Sandeep.")
    second = _chat(runtime_client, headers, "What is my name?")

    assert first["conversation_id"] != second["conversation_id"]
    assert "Your name is Sandeep." in second["response"]


def test_occupation_is_available_across_conversations(
    runtime_client: TestClient,
) -> None:
    _configure_chat_runtime(runtime_client)
    headers = _auth_headers(runtime_client, "work-user", "work-user@example.com")

    _chat(runtime_client, headers, "I am a Cloud Architect.")
    second = _chat(runtime_client, headers, "What do I do?")

    assert "You are a Cloud Architect." in second["response"]


def test_language_preference_is_available_across_conversations(
    runtime_client: TestClient,
) -> None:
    _configure_chat_runtime(runtime_client)
    headers = _auth_headers(
        runtime_client,
        "language-user",
        "language-user@example.com",
    )

    _chat(runtime_client, headers, "I prefer Python.")
    second = _chat(runtime_client, headers, "What language do I prefer?")

    assert "You prefer Python." in second["response"]


def test_persistent_memory_survives_backend_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_db = tmp_path / "restart-memory.db"
    rag_root = tmp_path / "restart-rag"
    enterprise_db = tmp_path / "restart-enterprise.db"
    conversation_db = tmp_path / "restart-conversations.db"

    monkeypatch.setenv("MEMORY_DB_PATH", str(memory_db))
    monkeypatch.setenv("RAG_DB_PATH", str(rag_root))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(enterprise_db))
    monkeypatch.setenv("CHAT_CONVERSATION_DB_PATH", str(conversation_db))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    with TestClient(app) as first_client:
        _configure_chat_runtime(first_client)
        headers = _auth_headers(
            first_client, "restart-user", "restart-user@example.com"
        )
        _chat(first_client, headers, "My name is Sandeep.")

    with TestClient(app) as second_client:
        _configure_chat_runtime(second_client)
        headers = _auth_headers(
            second_client, "restart-user", "restart-user@example.com"
        )
        result = _chat(second_client, headers, "What is my name?")

    assert "Your name is Sandeep." in result["response"]


def test_memory_persists_after_conversation_delete(runtime_client: TestClient) -> None:
    _configure_chat_runtime(runtime_client)
    headers = _auth_headers(
        runtime_client, "delete-memory", "delete-memory@example.com"
    )

    first = _chat(runtime_client, headers, "My name is Sandeep.")

    delete_response = runtime_client.delete(
        f"/chat/conversations/{first['conversation_id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["database_deleted"] is True

    second = _chat(runtime_client, headers, "What is my name?")
    assert second["conversation_id"] != first["conversation_id"]
    assert "Your name is Sandeep." in second["response"]
