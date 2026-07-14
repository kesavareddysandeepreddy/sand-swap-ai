from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_chat_service
from backend.api.main import app
from backend.auth.auth_service import AuthService
from backend.auth.password_hasher import PasswordHasher
from backend.auth.token_service import TokenService
from backend.persistence.sqlite_enterprise_repositories import (
    SQLiteProjectRepository,
    SQLiteUserRepository,
)
from backend.services.user_service import UserService


class FakeChatService:
    """Minimal chat service stub for API integration tests."""

    async def send_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        model: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, str]:
        _ = (model, workspace_id, project_id)
        return {
            "response": f"echo:{message}",
            "conversation_id": conversation_id or "default-conversation",
            "message_id": "fake-message",
        }

    async def list_conversations(
        self,
        *,
        user_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, object]]:
        _ = (user_id, workspace_id, project_id)
        return []


class FakeChatServiceWithModels(FakeChatService):
    """Chat service stub exposing deterministic model inventory."""

    def __init__(self) -> None:
        self.last_model: str | None = None
        self.ollama_client = type(
            "FakeOllamaClient",
            (),
            {
                "model": "llama3.2:3b",
                "list_models": lambda _self: ["llama3.2:3b", "qwen2.5:14b"],
            },
        )()

    async def send_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        model: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, str]:
        _ = (user_id, workspace_id, project_id)
        self.last_model = model
        return {
            "response": f"echo:{message}",
            "conversation_id": conversation_id or "default-conversation",
            "message_id": "fake-message",
        }


class FakeOwnershipService:
    def __init__(self) -> None:
        self.project_repository = type("ProjectRepo", (), {})()
        self.user_service = type(
            "UserService",
            (),
            {
                "get_active_project_id": lambda _self, _user_id: "workspace-user-1",
                "get_active_workspace_project_id": lambda _self, _user_id: (
                    "project-user-1"
                ),
                "set_active_project_id": lambda _self, _user_id, _project_id: None,
                "set_active_workspace_project_id": lambda _self, _user_id, _project_id: (
                    None
                ),
                "get_user": lambda _self, _user_id: object(),
            },
        )()

    def resolve_request_context(self, *, user_id: str) -> dict[str, str]:
        _ = user_id
        return {
            "user_id": "user-1",
            "workspace_id": "workspace-user-1",
            "project_id": "project-user-1",
        }

    def get_active_project_for_user(self, user_id: str):
        _ = user_id
        return type(
            "Project",
            (),
            {
                "id": "workspace-user-1",
                "name": "Personal Workspace",
                "description": "",
                "created_at": type("T", (), {"isoformat": lambda _self: ""})(),
            },
        )()

    def list_projects_for_user(self, user_id: str) -> list[object]:
        _ = user_id
        return [self.get_active_project_for_user(user_id)]


def test_google_user_provisioning_creates_personal_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enterprise_db = tmp_path / "enterprise.db"
    user_repository = SQLiteUserRepository(db_path=str(enterprise_db))
    project_repository = SQLiteProjectRepository(db_path=str(enterprise_db))
    user_service = UserService(
        user_repository=user_repository,
        project_repository=project_repository,
    )
    auth_service = AuthService(
        user_service=user_service,
        password_hasher=PasswordHasher(),
        token_service=TokenService(secret="test-secret"),
    )

    monkeypatch.setattr(
        AuthService,
        "verify_google_id_token",
        lambda self, *, id_token: {
            "sub": "google-sub-123",
            "email": "alice@example.com",
            "name": "Alice Example",
            "picture": "https://example.com/avatar.png",
        },
    )

    user = auth_service.authenticate_google_id_token(id_token="id-token")

    assert user.email == "alice@example.com"
    assert user.display_name == "Alice Example"
    assert user.google_subject_id == "google-sub-123"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert user.auth_provider == "google"

    stored_user = user_repository.get_by_email("alice@example.com")
    assert stored_user is not None
    assert stored_user.google_subject_id == "google-sub-123"
    assert stored_user.avatar_url == "https://example.com/avatar.png"
    assert stored_user.auth_provider == "google"

    projects = project_repository.list_by_owner(user.id)
    assert len(projects) == 1
    assert projects[0].name == "Personal Workspace"

    user_repository.close()
    project_repository.close()


def test_health_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The health endpoint should return the runtime metadata."""
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "health-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "health-rag"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "SandSwap AI"
    assert response.json()["version"] == "0.1.0"


def test_runtime_uses_disk_backed_memory_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live runtime should not register an in-memory SQLite store."""
    runtime_db_path = tmp_path / "runtime-memory.db"
    monkeypatch.setenv("MEMORY_DB_PATH", str(runtime_db_path))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "runtime-rag"))

    with TestClient(app):
        memory_store = app.state.container.resolve("memory_store")

    assert getattr(memory_store, "db_path", "") != ":memory:"
    assert Path(memory_store.db_path).is_absolute()
    assert memory_store.db_path == str(runtime_db_path.resolve())


def test_chat_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chat endpoint should return the chat-service payload."""
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-rag"))

    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/chat",
                json={
                    "user_id": "user-1",
                    "conversation_id": "conv-1",
                    "message": "hello",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["response"] == "echo:hello"
    assert response.json()["conversation_id"] == "conv-1"
    assert response.json()["memories_saved"] == 0


def test_chat_requires_anonymous_session_id_when_unauthenticated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-anon-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-anon-rag"))

    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/chat",
                json={
                    "message": "hello",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Anonymous session id is required"


def test_chat_ignores_forged_user_id_for_authenticated_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-auth-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-auth-rag"))

    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    try:
        with TestClient(app) as client:
            token_service = app.state.container.resolve("token_service")
            token = token_service.create_access_token("auth-user", "auth@example.com")
            response = client.post(
                "/chat",
                json={
                    "user_id": "forged-user",
                    "message": "hello",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "default-conversation"


def test_chat_models_endpoint_returns_available_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-models-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-models-rag"))

    app.dependency_overrides[get_chat_service] = lambda: FakeChatServiceWithModels()
    try:
        with TestClient(app) as client:
            response = client.get("/chat/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"models": ["llama3.2:3b", "qwen2.5:14b"]}


def test_chat_model_is_forwarded_from_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "chat-model-forward-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "chat-model-forward-rag"))

    fake_chat = FakeChatServiceWithModels()
    app.dependency_overrides[get_chat_service] = lambda: fake_chat
    try:
        with TestClient(app) as client:
            response = client.post(
                "/chat",
                json={
                    "user_id": "anon-session-1",
                    "message": "hello",
                    "model": "qwen2.5:14b",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_chat.last_model == "qwen2.5:14b"
