from __future__ import annotations

from pathlib import Path

from backend.knowledge_connector_store.models import ConnectorRecord
from backend.knowledge_connector_store.repository import ConnectorStoreRepository
from backend.knowledge_connector_store.service import ConnectorStoreService
from backend.knowledge_connectors.factory import ConnectorFactory
from backend.knowledge_connectors.manager import ConnectorManager
from backend.knowledge_connectors.registry import ConnectorRegistry
from backend.knowledge_connectors.upload_connector import UploadConnector
from backend.knowledge_sources.source_types import SourceType
from backend.upload_manager.pipeline import UploadPipeline
from backend.upload_manager.queue import UploadQueue
from backend.upload_manager.repository import UploadRepository
from backend.upload_manager.service import UploadManagerService


def _upload_manager() -> UploadManagerService:
    return UploadManagerService(
        repository=UploadRepository(),
        queue=UploadQueue(),
        pipeline=UploadPipeline(),
    )


def test_repository_create_update_delete_and_list_by_project(tmp_path: Path) -> None:
    db_path = str(tmp_path / "connector-store.db")
    repository = ConnectorStoreRepository(db_path=db_path)

    created = repository.create(
        ConnectorRecord(
            source_id="upload-default",
            source_type=SourceType.UPLOAD,
            name="Upload Connector",
        )
    )

    loaded = repository.get(created.id)
    assert loaded is not None
    assert loaded.source_type == SourceType.UPLOAD

    created.name = "Upload Connector Updated"
    updated = repository.update(created)
    assert updated.name == "Upload Connector Updated"

    items = repository.list_by_project(project_id="default")
    assert len(items) == 1
    assert items[0].id == created.id

    deleted = repository.delete(created.id)
    assert deleted is True
    assert repository.get(created.id) is None

    repository.close()


def test_service_create_update_enable_disable_and_project_listing(
    tmp_path: Path,
) -> None:
    repository = ConnectorStoreRepository(db_path=str(tmp_path / "service-store.db"))
    service = ConnectorStoreService(repository=repository)

    created = service.create_connector(
        source_id="source-1",
        source_type=SourceType.UPLOAD,
        name="Upload Connector",
        project_id="project-1",
        workspace_id="workspace-1",
        settings={"path": "uploads"},
        credentials_reference="secret://upload",
        credentials_provider="vault",
        credentials_metadata={"region": "local"},
    )
    assert created.configuration.project_id == "project-1"
    assert created.configuration.workspace_id == "workspace-1"

    updated = service.update_connector(
        record_id=created.id,
        name="Upload Connector v2",
        settings={"path": "uploads-v2"},
    )
    assert updated.name == "Upload Connector v2"
    assert updated.configuration.settings["path"] == "uploads-v2"

    disabled = service.disable_connector(record_id=created.id)
    assert disabled.enabled is False

    enabled = service.enable_connector(record_id=created.id)
    assert enabled.enabled is True

    items = service.list_connectors_by_project(project_id="project-1")
    assert len(items) == 1
    assert items[0].id == created.id

    deleted = service.delete_connector(record_id=created.id)
    assert deleted is True

    repository.close()


def test_service_persists_sync_metadata_and_statistics(tmp_path: Path) -> None:
    repository = ConnectorStoreRepository(db_path=str(tmp_path / "sync-store.db"))
    service = ConnectorStoreService(repository=repository)

    created = service.create_connector(
        source_id="source-1",
        source_type=SourceType.UPLOAD,
        name="Upload Connector",
        project_id="project-1",
    )

    sync_updated = service.persist_sync_metadata(
        record_id=created.id,
        status="success",
        cursor="cursor-1",
        metadata={"session_id": "session-1"},
        incremental=False,
    )
    assert sync_updated.sync_state.status == "success"
    assert sync_updated.sync_state.cursor == "cursor-1"
    assert sync_updated.sync_state.last_sync_at is not None

    incremental_updated = service.persist_sync_metadata(
        record_id=created.id,
        status="success",
        cursor="cursor-2",
        metadata={"session_id": "session-2"},
        incremental=True,
    )
    assert incremental_updated.sync_state.last_incremental_sync_at is not None

    stats_updated = service.persist_indexing_statistics(
        record_id=created.id,
        files_indexed=4,
        chunks_indexed=12,
        embeddings_indexed=12,
        errors_count=1,
        metadata={"source": "upload"},
    )
    assert stats_updated.statistics.files_indexed == 4
    assert stats_updated.statistics.chunks_indexed == 12
    assert stats_updated.statistics.embeddings_indexed == 12
    assert stats_updated.statistics.errors_count == 1

    repository.close()


def test_connector_manager_restores_connectors_from_store(tmp_path: Path) -> None:
    repository = ConnectorStoreRepository(db_path=str(tmp_path / "manager-store.db"))
    store_service = ConnectorStoreService(repository=repository)
    upload_manager = _upload_manager()

    manager = ConnectorManager(
        registry=ConnectorRegistry(),
        factory=ConnectorFactory(),
        store_service=store_service,
    )

    manager.bootstrap_default_connector(
        source_type=SourceType.UPLOAD,
        name="Upload Connector",
        project_id="project-1",
        workspace_id="workspace-1",
        settings={},
        source_id="source-1",
        builder=lambda: UploadConnector(upload_manager=upload_manager),
    )

    manager.restore_connectors()
    health = manager.health()
    assert SourceType.UPLOAD in health
    assert health[SourceType.UPLOAD].status in {"ok", "ready"}

    sync_job = manager.sync(
        source_type=SourceType.UPLOAD,
        config={
            "project_id": "project-1",
            "files": [
                {
                    "file_name": "alpha.txt",
                    "file_size": 1,
                    "mime_type": "text/plain",
                    "parser": "auto",
                }
            ],
        },
        source_id="source-1",
    )
    assert sync_job.status.value == "success"

    loaded = store_service.load_connectors()
    assert len(loaded) == 1
    assert loaded[0].sync_state.status == "success"
    assert loaded[0].statistics.files_indexed >= 0

    repository.close()
