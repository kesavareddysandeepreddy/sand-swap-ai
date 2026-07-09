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
