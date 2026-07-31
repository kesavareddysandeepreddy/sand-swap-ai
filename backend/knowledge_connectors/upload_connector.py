"""Upload connector implementation for local uploaded project files."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.knowledge_connectors.base import BaseConnector
from backend.knowledge_connectors.models import (
    ConnectorCapabilities,
    ConnectorConfiguration,
    ConnectorHealth,
    ConnectorMetadata,
    SyncJob,
)
from backend.upload_manager.service import UploadManagerService


class UploadConnector(BaseConnector):
    """Connector that exposes uploaded files as a knowledge source."""

    def __init__(self, *, upload_manager: UploadManagerService) -> None:
        super().__init__(
            metadata=ConnectorMetadata(
                key="upload",
                display_name="Upload",
                description="Local upload knowledge connector",
                tags=("upload", "local"),
            ),
            capabilities=ConnectorCapabilities(
                supports_discovery=True,
                supports_incremental_sync=True,
                supports_search=True,
                supports_list_items=True,
            ),
            configuration=ConnectorConfiguration(
                required_fields=(),
                secret_fields=(),
                defaults={},
            ),
        )
        self._upload_manager = upload_manager
        self._connected = False

    def connect(self, *, config: dict[str, Any]) -> bool:
        health = self._upload_manager.health()
        self._connected = str(health.get("status", "")).lower() == "ok"
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def validate(self, *, config: dict[str, Any]) -> tuple[bool, list[str]]:
        return self.configuration.validate(config)

    def discover(self, *, config: dict[str, Any]) -> list[dict[str, Any]]:
        session_id = str(config.get("session_id", "")).strip()
        if not session_id:
            return []
        session = self._upload_manager.get_session(session_id)
        if session is None:
            return []
        jobs = self._upload_manager.get_jobs(session_id)
        return [
            {
                "session_id": session.id,
                "project_id": session.project_id,
                "source_id": session.source_id,
                "status": session.status,
                "total_files": session.total_files,
                "processed_files": session.processed_files,
                "jobs": [
                    {
                        "id": job.id,
                        "file_name": job.file_name,
                        "status": job.status,
                    }
                    for job in jobs
                ],
            }
        ]

    def sync(self, *, config: dict[str, Any], source_id: str) -> SyncJob:
        job = SyncJob(
            connector_key=self.metadata.key,
            source_id=source_id,
            full_sync=True,
        )
        job.mark_running()
        try:
            project_id = str(config.get("project_id", "default")).strip() or "default"
            files = config.get("files", [])
            if not isinstance(files, list):
                files = []

            session = self._upload_manager.create_session(
                project_id=project_id,
                source_id=source_id,
                total_files=0,
                metadata={"connector": self.metadata.key},
            )
            queued_jobs = self._upload_manager.enqueue_jobs(session.id, files)
            for queued in queued_jobs:
                self._upload_manager.process_job(queued.id)

            progress = self._upload_manager.progress(session.id)
            processed = int(progress.get("processed_files", 0))
            job.metadata = {
                "session_id": session.id,
                "queued_jobs": len(queued_jobs),
                "progress": progress,
            }
            job.mark_success(items_processed=processed)
        except Exception as exc:  # noqa: BLE001
            job.mark_failed(str(exc))
        return job

    def incremental_sync(
        self,
        *,
        config: dict[str, Any],
        source_id: str,
        cursor: str | None = None,
    ) -> SyncJob:
        job = SyncJob(
            connector_key=self.metadata.key,
            source_id=source_id,
            full_sync=False,
            metadata={"cursor": cursor or ""},
        )
        job.mark_running()
        job.mark_success(items_processed=0)
        return job

    def health(self) -> ConnectorHealth:
        manager_health = self._upload_manager.health()
        status = str(manager_health.get("status", "unknown"))
        return ConnectorHealth(
            status=status,
            connected=self._connected,
            last_checked_at=datetime.now(UTC),
            message="Upload connector delegated to UploadManagerService",
            details=dict(manager_health),
        )

    def search(
        self,
        *,
        config: dict[str, Any],
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        session_id = str(config.get("session_id", "")).strip()
        if not session_id:
            return []
        items: list[dict[str, Any]] = []
        for job in self._upload_manager.get_jobs(session_id):
            if query.lower() in job.file_name.lower():
                items.append(
                    {
                        "id": job.id,
                        "file_name": job.file_name,
                        "status": job.status,
                        "file_size": job.file_size,
                    }
                )
            if len(items) >= limit:
                break
        return items

    def list_items(
        self,
        *,
        config: dict[str, Any],
        page_size: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        _ = (config, page_size, cursor)
        return []
