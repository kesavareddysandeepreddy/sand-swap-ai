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
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "project-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "project-rag"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "project-enterprise.db"))
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


def test_project_crud_and_switch(runtime_client: TestClient) -> None:
    headers = _auth_headers(runtime_client, "project-user", "project-user@example.com")

    projects = runtime_client.get("/auth/projects", headers=headers)
    assert projects.status_code == 200
    initial = projects.json()
    assert len(initial) == 1
    assert initial[0]["is_active"] is True
    default_project_id = initial[0]["id"]

    created = runtime_client.post(
        "/auth/projects",
        json={"name": "Team Project", "set_active": True},
        headers=headers,
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["name"] == "Team Project"
    assert created_body["is_active"] is True

    renamed = runtime_client.patch(
        f"/auth/projects/{created_body['id']}",
        json={"name": "Renamed Project"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed Project"

    switched = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": default_project_id},
        headers=headers,
    )
    assert switched.status_code == 200
    assert switched.json()["id"] == default_project_id
    assert switched.json()["is_active"] is True

    deleted = runtime_client.delete(
        f"/auth/projects/{created_body['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}


def test_project_access_denied_across_users(runtime_client: TestClient) -> None:
    owner_headers = _auth_headers(runtime_client, "owner", "owner@example.com")
    intruder_headers = _auth_headers(runtime_client, "intruder", "intruder@example.com")

    projects = runtime_client.get("/auth/projects", headers=owner_headers)
    assert projects.status_code == 200
    owner_project_id = projects.json()[0]["id"]

    switch = runtime_client.post(
        "/auth/projects/switch",
        json={"project_id": owner_project_id},
        headers=intruder_headers,
    )
    assert switch.status_code == 404

    delete = runtime_client.delete(
        f"/auth/projects/{owner_project_id}",
        headers=intruder_headers,
    )
    assert delete.status_code == 404


def test_project_cannot_delete_last(runtime_client: TestClient) -> None:
    headers = _auth_headers(
        runtime_client, "single-project", "single-project@example.com"
    )
    projects = runtime_client.get("/auth/projects", headers=headers)
    assert projects.status_code == 200
    project_id = projects.json()[0]["id"]

    deleted = runtime_client.delete(f"/auth/projects/{project_id}", headers=headers)
    assert deleted.status_code == 400
    assert deleted.json()["detail"] == "Cannot delete the last project"


def test_projects_are_scoped_within_workspace(runtime_client: TestClient) -> None:
    headers = _auth_headers(
        runtime_client, "workspace-project-user", "workspace-project@example.com"
    )

    workspace_one = runtime_client.get("/auth/session", headers=headers)
    assert workspace_one.status_code == 200
    workspace_one_id = workspace_one.json()["workspace_id"]

    created_workspace = runtime_client.post(
        "/auth/workspaces",
        json={"name": "Workspace Two", "set_active": False},
        headers=headers,
    )
    assert created_workspace.status_code == 200
    workspace_two_id = created_workspace.json()["id"]

    create_project_one = runtime_client.post(
        "/auth/projects",
        json={"name": "Workspace One Project", "set_active": True},
        headers=headers,
    )
    assert create_project_one.status_code == 200
    project_one_id = create_project_one.json()["id"]

    switch_workspace = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": workspace_two_id},
        headers=headers,
    )
    assert switch_workspace.status_code == 200

    create_project_two = runtime_client.post(
        "/auth/projects",
        json={"name": "Workspace Two Project", "set_active": True},
        headers=headers,
    )
    assert create_project_two.status_code == 200
    project_two_id = create_project_two.json()["id"]

    list_two = runtime_client.get("/auth/projects", headers=headers)
    assert list_two.status_code == 200
    assert {item["id"] for item in list_two.json()} == {
        item["id"] for item in list_two.json()
    }
    assert {item["id"] for item in list_two.json()} != {project_one_id}
    assert project_two_id in {item["id"] for item in list_two.json()}

    switch_back = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": workspace_one_id},
        headers=headers,
    )
    assert switch_back.status_code == 200

    list_one = runtime_client.get("/auth/projects", headers=headers)
    assert list_one.status_code == 200
    assert project_one_id in {item["id"] for item in list_one.json()}
    assert project_two_id not in {item["id"] for item in list_one.json()}
