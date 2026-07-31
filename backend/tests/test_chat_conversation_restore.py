from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.chat.domain.conversation import Conversation
from backend.domain.entities.ownership import ConversationOwner


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
    monkeypatch.setenv(
        "CHAT_CONVERSATION_DB_PATH",
        str(tmp_path / "chat-conversation-restore-conversations.db"),
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


def _delete_conversation(
    client: TestClient,
    headers: dict[str, str],
    conversation_id: str,
) -> dict[str, object]:
    response = client.delete(f"/chat/conversations/{conversation_id}", headers=headers)
    assert response.status_code == 200
    return response.json()


def _delete_conversation_without_auth(
    client: TestClient,
    conversation_id: str,
) -> dict[str, object]:
    response = client.delete(f"/chat/conversations/{conversation_id}")
    assert response.status_code == 200
    return response.json()


def _db_conversation_ids(
    client: TestClient,
    user_id: str,
) -> set[str]:
    db_path = Path(client.app.state.container.resolve("conversation_store").db_path)
    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(
            "SELECT id FROM conversations WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {str(row[0]) for row in rows}


def _db_owner_row(
    client: TestClient,
    conversation_id: str,
) -> tuple[str, str, str, str] | None:
    db_path = Path(
        client.app.state.container.resolve(
            "enterprise_conversation_owner_repository"
        ).db_path
    )
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute(
            """
            SELECT conversation_id, user_id, workspace_id, project_id
            FROM enterprise_conversation_owners
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), str(row[2]), str(row[3]))


def _seed_legacy_conversation(
    client: TestClient,
    user_id: str,
    conversation_id: str,
    message: str,
) -> None:
    conversation = Conversation(id=conversation_id, user_id=user_id)
    conversation.add_message("user", message)
    db_path = Path(client.app.state.container.resolve("conversation_store").db_path)
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, user_id, created_at, updated_at, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation.id,
                conversation.user_id,
                conversation.created_at.isoformat(),
                conversation.updated_at.isoformat(),
                json.dumps(conversation.to_dict()),
            ),
        )
        connection.commit()


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


def test_deleted_conversation_is_not_restored_after_refresh(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "delete-user",
        "delete-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    conversation_id = _chat(runtime_client, headers, "Delete me")
    listed_before = _list_conversations(runtime_client, headers)
    assert conversation_id in {item["id"] for item in listed_before}

    deleted = _delete_conversation(runtime_client, headers, conversation_id)
    assert deleted["conversation_id"] == conversation_id
    assert deleted["deleted"] is True
    assert deleted["database_deleted"] is True

    listed_after_delete = _list_conversations(runtime_client, headers)
    assert conversation_id not in {item["id"] for item in listed_after_delete}

    # Simulate refresh/new hydration by listing again.
    listed_after_refresh = _list_conversations(runtime_client, headers)
    assert conversation_id not in {item["id"] for item in listed_after_refresh}


def test_create_delete_then_list_has_zero_matching_conversations(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "delete-list-user",
        "delete-list-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    created_conversation_id = _chat(
        runtime_client,
        headers,
        "create then delete",
    )
    deleted = _delete_conversation(
        runtime_client,
        headers,
        created_conversation_id,
    )
    assert deleted["database_deleted"] is True

    listed_after_delete = _list_conversations(runtime_client, headers)
    matching_ids = [
        item["id"]
        for item in listed_after_delete
        if item["id"] == created_conversation_id
    ]
    assert matching_ids == []


def test_deleting_scoped_conversation_removes_legacy_id_record(
    runtime_client: TestClient,
) -> None:
    user_id = "legacy-delete-user"
    headers = _auth_headers(
        runtime_client,
        user_id,
        "legacy-delete-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    legacy_id = "legacy-conversation"
    _seed_legacy_conversation(
        runtime_client,
        user_id,
        legacy_id,
        "legacy seeded message",
    )

    scoped_id = _chat(
        runtime_client,
        headers,
        "continue legacy thread",
        conversation_id=legacy_id,
    )
    assert scoped_id == f"{user_id}:{legacy_id}"

    listed_before_delete = {
        item["id"] for item in _list_conversations(runtime_client, headers)
    }
    assert scoped_id in listed_before_delete
    assert legacy_id not in listed_before_delete

    deleted = _delete_conversation(runtime_client, headers, scoped_id)
    assert deleted["database_deleted"] is True

    listed_after_delete = {
        item["id"] for item in _list_conversations(runtime_client, headers)
    }
    assert scoped_id not in listed_after_delete
    assert legacy_id not in listed_after_delete

    db_after_delete = _db_conversation_ids(runtime_client, user_id)
    assert scoped_id not in db_after_delete
    assert legacy_id not in db_after_delete


def test_chat_history_is_restored_after_backend_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_db = tmp_path / "chat-restart-memory.db"
    rag_root = tmp_path / "chat-restart-rag"
    enterprise_db = tmp_path / "chat-restart-enterprise.db"
    conversation_db = tmp_path / "chat-restart-conversations.db"

    monkeypatch.setenv("MEMORY_DB_PATH", str(memory_db))
    monkeypatch.setenv("RAG_DB_PATH", str(rag_root))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(enterprise_db))
    monkeypatch.setenv("CHAT_CONVERSATION_DB_PATH", str(conversation_db))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    with TestClient(app) as first_client:
        headers = _auth_headers(
            first_client,
            "restart-user",
            "restart-user@example.com",
        )
        _set_ollama_echo(first_client)
        conversation_id = _chat(first_client, headers, "Hello before restart")
        _chat(first_client, headers, "Second message", conversation_id=conversation_id)

    with TestClient(app) as second_client:
        headers = _auth_headers(
            second_client,
            "restart-user",
            "restart-user@example.com",
        )
        listed = _list_conversations(second_client, headers)
        restored = next(item for item in listed if item["id"] == conversation_id)
        assert len(restored["messages"]) >= 4


def test_list_conversations_matches_persistent_repository(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "db-sync-user",
        "db-sync-user@example.com",
    )
    _set_ollama_echo(runtime_client)

    first = _chat(runtime_client, headers, "Conversation one")
    second = _chat(runtime_client, headers, "Conversation two")
    api_ids = {item["id"] for item in _list_conversations(runtime_client, headers)}
    db_ids = _db_conversation_ids(runtime_client, "db-sync-user")

    assert first in api_ids
    assert second in api_ids
    assert api_ids == db_ids

    _delete_conversation(runtime_client, headers, first)
    api_after_delete = {
        item["id"] for item in _list_conversations(runtime_client, headers)
    }
    db_after_delete = _db_conversation_ids(runtime_client, "db-sync-user")
    assert first not in api_after_delete
    assert first not in db_after_delete
    assert api_after_delete == db_after_delete


def test_authenticated_delete_removes_conversation_owner_cache_and_list_visibility(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "google-auth-delete-user",
        "google-auth-delete@example.com",
    )
    _set_ollama_echo(runtime_client)

    session = runtime_client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    authenticated_user_id = str(session.json()["user_id"])
    workspace_id = str(session.json()["workspace_id"])
    project_id = str(session.json()["project_id"])

    scoped_headers = {
        **headers,
        "X-Workspace-Id": workspace_id,
        "X-Project-Id": project_id,
    }

    created = runtime_client.post(
        "/chat",
        headers=scoped_headers,
        json={"message": "Authenticated delete trace"},
    )
    assert created.status_code == 200
    conversation_id = str(created.json()["conversation_id"])

    # Trace tuple requested by the investigation.
    assert conversation_id.startswith(f"{authenticated_user_id}:")
    assert authenticated_user_id
    assert workspace_id
    assert project_id

    before_delete_conversation_row = conversation_id in _db_conversation_ids(
        runtime_client,
        authenticated_user_id,
    )
    before_delete_owner_row = _db_owner_row(runtime_client, conversation_id)
    before_delete_cache_entry = (
        authenticated_user_id,
        conversation_id,
    ) in runtime_client.app.state.container.resolve(
        "chat_service"
    ).session_manager._sessions

    assert before_delete_conversation_row is True
    assert before_delete_owner_row is not None
    assert before_delete_cache_entry is True
    assert before_delete_owner_row[1] == authenticated_user_id
    assert before_delete_owner_row[2] == workspace_id
    assert before_delete_owner_row[3] == project_id

    deleted = runtime_client.delete(
        f"/chat/conversations/{conversation_id}",
        headers=scoped_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["database_deleted"] is True

    after_delete_conversation_row = conversation_id in _db_conversation_ids(
        runtime_client,
        authenticated_user_id,
    )
    after_delete_owner_row = _db_owner_row(runtime_client, conversation_id)
    after_delete_cache_entry = (
        authenticated_user_id,
        conversation_id,
    ) in runtime_client.app.state.container.resolve(
        "chat_service"
    ).session_manager._sessions

    assert after_delete_conversation_row is False
    assert after_delete_owner_row is None
    assert after_delete_cache_entry is False

    listed = runtime_client.get("/chat/conversations", headers=scoped_headers)
    assert listed.status_code == 200
    listed_ids = {item["id"] for item in listed.json()["items"]}
    assert conversation_id not in listed_ids


def test_list_conversations_prunes_orphan_owner_rows(
    runtime_client: TestClient,
) -> None:
    headers = _auth_headers(
        runtime_client,
        "orphan-owner-user",
        "orphan-owner@example.com",
    )
    session = runtime_client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    user_id = str(session.json()["user_id"])
    workspace_id = str(session.json()["workspace_id"])
    project_id = str(session.json()["project_id"])

    orphan_conversation_id = f"{user_id}:orphan-legacy-conversation"
    ownership_repository = runtime_client.app.state.container.resolve(
        "enterprise_conversation_owner_repository"
    )
    ownership_repository.save(
        ConversationOwner(
            conversation_id=orphan_conversation_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    )
    assert _db_owner_row(runtime_client, orphan_conversation_id) is not None

    scoped_headers = {
        **headers,
        "X-Workspace-Id": workspace_id,
        "X-Project-Id": project_id,
    }
    listed = runtime_client.get("/chat/conversations", headers=scoped_headers)
    assert listed.status_code == 200
    listed_ids = {item["id"] for item in listed.json()["items"]}
    assert orphan_conversation_id not in listed_ids

    assert _db_owner_row(runtime_client, orphan_conversation_id) is None


def test_authenticated_delete_then_restart_keeps_conversation_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_db = tmp_path / "auth-delete-restart-memory.db"
    rag_root = tmp_path / "auth-delete-restart-rag"
    enterprise_db = tmp_path / "auth-delete-restart-enterprise.db"
    conversation_db = tmp_path / "auth-delete-restart-conversations.db"

    monkeypatch.setenv("MEMORY_DB_PATH", str(memory_db))
    monkeypatch.setenv("RAG_DB_PATH", str(rag_root))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(enterprise_db))
    monkeypatch.setenv("CHAT_CONVERSATION_DB_PATH", str(conversation_db))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    with TestClient(app) as first_client:
        headers = _auth_headers(
            first_client,
            "auth-delete-restart-user",
            "auth-delete-restart@example.com",
        )
        _set_ollama_echo(first_client)

        session = first_client.get("/auth/session", headers=headers)
        assert session.status_code == 200
        scoped_headers = {
            **headers,
            "X-Workspace-Id": str(session.json()["workspace_id"]),
            "X-Project-Id": str(session.json()["project_id"]),
        }

        created = first_client.post(
            "/chat",
            headers=scoped_headers,
            json={"message": "Auth delete before restart"},
        )
        assert created.status_code == 200
        conversation_id = created.json()["conversation_id"]

        deleted = first_client.delete(
            f"/chat/conversations/{conversation_id}",
            headers=scoped_headers,
        )
        assert deleted.status_code == 200
        assert deleted.json()["database_deleted"] is True

    with TestClient(app) as second_client:
        headers = _auth_headers(
            second_client,
            "auth-delete-restart-user",
            "auth-delete-restart@example.com",
        )
        session = second_client.get("/auth/session", headers=headers)
        assert session.status_code == 200
        scoped_headers = {
            **headers,
            "X-Workspace-Id": str(session.json()["workspace_id"]),
            "X-Project-Id": str(session.json()["project_id"]),
        }
        listed = second_client.get("/chat/conversations", headers=scoped_headers)
        assert listed.status_code == 200
        assert conversation_id not in {item["id"] for item in listed.json()["items"]}


def test_anonymous_create_delete_does_not_reappear_after_refresh(
    runtime_client: TestClient,
) -> None:
    anon_user_id = "anon-test-session-123"
    _set_ollama_echo(runtime_client)

    # Create + send one message as anonymous user.
    response = runtime_client.post(
        "/chat",
        json={"user_id": anon_user_id, "message": "Hello"},
    )
    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]
    assert conversation_id.startswith(f"{anon_user_id}:")

    db_before_delete = _db_conversation_ids(runtime_client, anon_user_id)
    assert conversation_id in db_before_delete

    deleted = _delete_conversation_without_auth(runtime_client, conversation_id)
    assert deleted["conversation_id"] == conversation_id
    assert deleted["deleted"] is True
    assert deleted["database_deleted"] is True

    db_after_delete = _db_conversation_ids(runtime_client, anon_user_id)
    assert conversation_id not in db_after_delete

    # Simulate refresh by reading storage-backed API state again.
    db_after_refresh = _db_conversation_ids(runtime_client, anon_user_id)
    assert conversation_id not in db_after_refresh


def test_anonymous_create_then_restart_preserves_conversation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_db = tmp_path / "anon-restart-memory.db"
    rag_root = tmp_path / "anon-restart-rag"
    enterprise_db = tmp_path / "anon-restart-enterprise.db"
    conversation_db = tmp_path / "anon-restart-conversations.db"

    monkeypatch.setenv("MEMORY_DB_PATH", str(memory_db))
    monkeypatch.setenv("RAG_DB_PATH", str(rag_root))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(enterprise_db))
    monkeypatch.setenv("CHAT_CONVERSATION_DB_PATH", str(conversation_db))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    anon_user_id = "anon-restart-user"

    with TestClient(app) as first_client:
        _set_ollama_echo(first_client)
        created = first_client.post(
            "/chat",
            json={"user_id": anon_user_id, "message": "Persist me"},
        )
        assert created.status_code == 200
        conversation_id = created.json()["conversation_id"]
        assert conversation_id in _db_conversation_ids(first_client, anon_user_id)

    with TestClient(app) as second_client:
        assert conversation_id in _db_conversation_ids(second_client, anon_user_id)


def test_anonymous_delete_then_restart_keeps_conversation_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_db = tmp_path / "anon-delete-restart-memory.db"
    rag_root = tmp_path / "anon-delete-restart-rag"
    enterprise_db = tmp_path / "anon-delete-restart-enterprise.db"
    conversation_db = tmp_path / "anon-delete-restart-conversations.db"

    monkeypatch.setenv("MEMORY_DB_PATH", str(memory_db))
    monkeypatch.setenv("RAG_DB_PATH", str(rag_root))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(enterprise_db))
    monkeypatch.setenv("CHAT_CONVERSATION_DB_PATH", str(conversation_db))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")

    anon_user_id = "anon-delete-restart-user"

    with TestClient(app) as first_client:
        _set_ollama_echo(first_client)
        created = first_client.post(
            "/chat",
            json={"user_id": anon_user_id, "message": "Delete then restart"},
        )
        assert created.status_code == 200
        conversation_id = created.json()["conversation_id"]

        deleted = first_client.delete(f"/chat/conversations/{conversation_id}")
        assert deleted.status_code == 200
        assert deleted.json()["database_deleted"] is True
        assert conversation_id not in _db_conversation_ids(first_client, anon_user_id)

    with TestClient(app) as second_client:
        assert conversation_id not in _db_conversation_ids(second_client, anon_user_id)
