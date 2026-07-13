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
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory-workspace.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "workspace-rag"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "workspace-enterprise.db"))
    with TestClient(app) as client:
        yield client


def _register_login_headers(
    client: TestClient, email: str, user_name: str
) -> dict[str, str]:
    user_service = client.app.state.container.resolve("user_service")
    user_id = email.split("@", 1)[0]
    existing = user_service.get_user_by_email(email)
    if existing is None:
        user_service.create_user(
            user_id=user_id,
            email=email,
            display_name=user_name,
        )
    else:
        user_id = existing.id

    token_service = client.app.state.container.resolve("token_service")
    token = token_service.create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


def test_workspace_crud_and_switch(runtime_client: TestClient) -> None:
    headers = _register_login_headers(
        runtime_client,
        "workspace-owner@example.com",
        "Workspace Owner",
    )

    list_response = runtime_client.get("/auth/workspaces", headers=headers)
    assert list_response.status_code == 200
    initial = list_response.json()
    assert len(initial) == 1
    assert initial[0]["is_active"] is True
    default_id = initial[0]["id"]

    create_response = runtime_client.post(
        "/auth/workspaces",
        json={"name": "Team Workspace", "set_active": True},
        headers=headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Team Workspace"
    assert created["is_active"] is True

    rename_response = runtime_client.patch(
        f"/auth/workspaces/{created['id']}",
        json={"name": "Renamed Workspace"},
        headers=headers,
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["name"] == "Renamed Workspace"

    switch_response = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": default_id},
        headers=headers,
    )
    assert switch_response.status_code == 200
    assert switch_response.json()["id"] == default_id
    assert switch_response.json()["is_active"] is True

    delete_response = runtime_client.delete(
        f"/auth/workspaces/{created['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}


def test_workspace_access_denied_across_users(runtime_client: TestClient) -> None:
    owner_headers = _register_login_headers(
        runtime_client,
        "owner@example.com",
        "Owner",
    )
    intruder_headers = _register_login_headers(
        runtime_client,
        "intruder@example.com",
        "Intruder",
    )

    owner_workspace = runtime_client.get("/auth/workspaces", headers=owner_headers)
    assert owner_workspace.status_code == 200
    owner_workspace_id = owner_workspace.json()[0]["id"]

    intruder_switch = runtime_client.post(
        "/auth/workspaces/switch",
        json={"workspace_id": owner_workspace_id},
        headers=intruder_headers,
    )
    assert intruder_switch.status_code == 404

    intruder_delete = runtime_client.delete(
        f"/auth/workspaces/{owner_workspace_id}",
        headers=intruder_headers,
    )
    assert intruder_delete.status_code == 404


def test_workspace_cannot_delete_last(runtime_client: TestClient) -> None:
    headers = _register_login_headers(
        runtime_client,
        "single@example.com",
        "Single",
    )
    workspace = runtime_client.get("/auth/workspaces", headers=headers)
    assert workspace.status_code == 200
    workspace_id = workspace.json()[0]["id"]

    delete = runtime_client.delete(f"/auth/workspaces/{workspace_id}", headers=headers)
    assert delete.status_code == 400
    assert delete.json()["detail"] == "Cannot delete the last workspace"
