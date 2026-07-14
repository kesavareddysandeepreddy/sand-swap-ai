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
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "documents-enterprise.db"))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "mock")
    with TestClient(app) as client:
        yield client


def test_document_upload_list_get_delete(runtime_client: TestClient) -> None:
    upload = runtime_client.post(
        "/documents/upload",
        files={
            "file": (
                "notes.md",
                b"# Title\n\nThis is a deployment guide.",
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 201
    document = upload.json()

    listing = runtime_client.get("/documents")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    fetched = runtime_client.get(f"/documents/{document['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "notes.md"

    chunks = runtime_client.get(f"/documents/{document['id']}/chunks")
    assert chunks.status_code == 200
    assert len(chunks.json()) >= 1

    retrieval = runtime_client.post(
        "/documents/retrieve",
        json={"query": "deployment guide", "top_k": 3},
    )
    assert retrieval.status_code == 200
    assert len(retrieval.json()["chunks"]) >= 1

    deleted = runtime_client.delete(f"/documents/{document['id']}")
    assert deleted.status_code == 204

    after = runtime_client.get("/documents")
    assert after.status_code == 200
    assert after.json() == []


def test_document_delete_all(runtime_client: TestClient) -> None:
    runtime_client.post(
        "/documents/upload",
        files={"file": ("one.txt", b"alpha", "text/plain")},
    )
    runtime_client.post(
        "/documents/upload",
        files={"file": ("two.txt", b"beta", "text/plain")},
    )

    response = runtime_client.delete("/documents")
    assert response.status_code == 200
    assert response.json()["deleted"] == 2


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


def test_documents_are_scoped_to_active_workspace(runtime_client: TestClient) -> None:
    headers = _auth_headers(runtime_client, "doc-user", "doc-user@example.com")

    primary = runtime_client.get("/auth/session", headers=headers)
    assert primary.status_code == 200
    primary_workspace = primary.json()["workspace_id"]
    primary_project = primary.json()["project_id"]

    secondary = runtime_client.post(
        "/auth/workspaces",
        json={"name": "Secondary Docs", "set_active": False},
        headers=headers,
    )
    assert secondary.status_code == 200
    secondary_workspace = secondary.json()["id"]

    first_upload = runtime_client.post(
        "/documents/upload",
        files={"file": ("one.txt", b"workspace one data", "text/plain")},
        headers=headers,
    )
    assert first_upload.status_code == 201

    switch = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": secondary_workspace},
        headers=headers,
    )
    assert switch.status_code == 200

    second_upload = runtime_client.post(
        "/documents/upload",
        files={"file": ("two.txt", b"workspace two data", "text/plain")},
        headers=headers,
    )
    assert second_upload.status_code == 201

    list_secondary = runtime_client.get("/documents", headers=headers)
    assert list_secondary.status_code == 200
    assert [item["name"] for item in list_secondary.json()] == ["two.txt"]

    switch_back = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": primary_workspace},
        headers=headers,
    )
    assert switch_back.status_code == 200

    switch_project = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": primary_project},
        headers=headers,
    )
    assert switch_project.status_code == 200

    list_primary = runtime_client.get("/documents", headers=headers)
    assert list_primary.status_code == 200
    assert [item["name"] for item in list_primary.json()] == ["one.txt"]
