from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.knowledge_connector_store.repository import ConnectorStoreRepository
from backend.knowledge_connector_store.service import ConnectorStoreService
from backend.knowledge_sources.models import KnowledgeSource
from backend.knowledge_sources.registry import ConnectorRegistry
from backend.knowledge_sources.repository import KnowledgeSourceRepository
from backend.knowledge_sources.service import KnowledgeSourceService
from backend.knowledge_sources.source_types import SourceType
from backend.rag.application.document_service import DocumentIngestionService
from backend.upload_manager.pipeline import UploadPipeline
from backend.upload_manager.queue import UploadQueue
from backend.upload_manager.repository import UploadRepository
from backend.upload_manager.service import UploadManagerService


def _build_upload_manager() -> UploadManagerService:
    return UploadManagerService(
        repository=UploadRepository(),
        queue=UploadQueue(),
        pipeline=UploadPipeline(),
    )


def _build_connector_store_service() -> ConnectorStoreService:
    repository = ConnectorStoreRepository(db_path=":memory:")
    return ConnectorStoreService(repository=repository)


def _build_ingestion_service() -> DocumentIngestionService:
    return MagicMock(spec=DocumentIngestionService)


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "knowledge-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "knowledge-rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "knowledge-enterprise.db"))
    with TestClient(app) as client:
        yield client


def test_repository_add_list_get_enable_disable_delete() -> None:
    repository = KnowledgeSourceRepository(db_path=":memory:")
    source = KnowledgeSource(
        project_id="project-1",
        name="Project Uploads",
        source_type=SourceType.UPLOAD,
    )
    stored = repository.add(source)

    listed = repository.list("project-1")
    assert len(listed) == 1
    assert listed[0].id == stored.id

    loaded = repository.get(stored.id)
    assert loaded is not None
    assert loaded.name == "Project Uploads"

    disabled = repository.disable(stored.id)
    assert disabled.enabled is False

    enabled = repository.enable(stored.id)
    assert enabled.enabled is True

    deleted = repository.delete(stored.id)
    assert deleted is True
    assert repository.get(stored.id) is None


def test_service_create_toggle_stats_and_health() -> None:
    repository = KnowledgeSourceRepository(db_path=":memory:")
    registry = ConnectorRegistry(
        upload_manager=_build_upload_manager(),
        ingestion_service=_build_ingestion_service(),
        store_service=_build_connector_store_service(),
    )
    service = KnowledgeSourceService(
        repository=repository,
        connector_registry=registry,
    )

    created = service.create_source(
        project_id="project-1",
        name="GitHub Repo",
        source_type=SourceType.GITHUB,
    )
    assert created.status == "configured"

    disabled = service.disable_source(created.id)
    assert disabled.enabled is False
    assert disabled.status == "disabled"

    enabled = service.enable_source(created.id)
    assert enabled.enabled is True
    assert enabled.status == "enabled"

    stats = service.update_statistics(
        source_id=created.id,
        file_count=11,
        chunk_count=22,
        embedding_count=33,
    )
    assert stats.file_count == 11
    assert stats.chunk_count == 22
    assert stats.embedding_count == 33
    assert stats.last_sync is not None

    health = service.health()
    assert health["status"] == "ok"
    assert health["connectors_total"] == len(SourceType)


def test_registry_contains_all_source_types() -> None:
    registry = ConnectorRegistry(
        upload_manager=_build_upload_manager(),
        ingestion_service=_build_ingestion_service(),
        store_service=_build_connector_store_service(),
    )
    connectors = registry.list_connectors()
    assert len(connectors) == len(SourceType)
    for source_type in SourceType:
        connector = registry.get_connector(source_type)
        if source_type == SourceType.UPLOAD:
            assert connector.metadata.key == "upload"
            assert connector.metadata.display_name == "Upload"
        elif source_type == SourceType.GITHUB:
            assert connector.metadata.key == "github"
            assert connector.metadata.display_name == "GitHub"
        elif source_type == SourceType.SHAREPOINT:
            assert connector.metadata.key == "sharepoint"
            assert connector.metadata.display_name == "SharePoint"


def test_registry_exposes_connector_manager_with_upload_registered() -> None:
    registry = ConnectorRegistry(
        upload_manager=_build_upload_manager(),
        ingestion_service=_build_ingestion_service(),
        store_service=_build_connector_store_service(),
    )
    manager = registry.manager
    assert manager.has_connector(SourceType.UPLOAD) is True
    assert manager.has_connector(SourceType.GITHUB) is True
    assert manager.has_connector(SourceType.SHAREPOINT) is True


def test_upload_connector_delegates_sync_discover_search() -> None:
    upload_manager = _build_upload_manager()
    registry = ConnectorRegistry(
        upload_manager=upload_manager,
        ingestion_service=_build_ingestion_service(),
        store_service=_build_connector_store_service(),
    )
    connector = registry.get_connector(SourceType.UPLOAD)

    assert connector.connect(config={}) is True
    sync_job = connector.sync(
        config={
            "project_id": "project-1",
            "files": [
                {
                    "file_name": "report-alpha.txt",
                    "file_size": 10,
                    "mime_type": "text/plain",
                    "parser": "auto",
                },
                {
                    "file_name": "report-beta.txt",
                    "file_size": 20,
                    "mime_type": "text/plain",
                    "parser": "auto",
                },
            ],
        },
        source_id="source-1",
    )
    assert sync_job.status.value == "success"
    session_id = str(sync_job.metadata.get("session_id", ""))
    assert session_id

    discovered = connector.discover(config={"session_id": session_id})
    assert len(discovered) == 1
    assert discovered[0]["source_id"] == "source-1"

    searched = connector.search(
        config={"session_id": session_id},
        query="alpha",
        limit=10,
    )
    assert len(searched) == 1
    assert searched[0]["file_name"] == "report-alpha.txt"


def test_api_knowledge_sources_crud_toggle_and_health(
    runtime_client: TestClient,
) -> None:
    create_response = runtime_client.post(
        "/api/knowledge-sources",
        json={
            "project_id": "project-1",
            "name": "Upload Source",
            "source_type": "Upload",
            "connection_config": {"path": "uploads"},
            "metadata": {"label": "default"},
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    source_id = created["id"]
    assert created["project_id"] == "project-1"
    assert created["source_type"] == "Upload"

    list_response = runtime_client.get(
        "/api/knowledge-sources",
        params={"project_id": "project-1"},
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == source_id

    disable_response = runtime_client.put(f"/api/knowledge-sources/{source_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False
    assert disable_response.json()["status"] == "disabled"

    enable_response = runtime_client.put(f"/api/knowledge-sources/{source_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True
    assert enable_response.json()["status"] == "enabled"

    health_response = runtime_client.get("/api/knowledge-sources/health")
    assert health_response.status_code == 200
    health = health_response.json()
    assert health["status"] == "ok"
    assert health["connectors_total"] == len(SourceType)

    delete_response = runtime_client.delete(f"/api/knowledge-sources/{source_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    not_found = runtime_client.delete(f"/api/knowledge-sources/{source_id}")
    assert not_found.status_code == 404
