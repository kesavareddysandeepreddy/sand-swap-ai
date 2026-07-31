"""Upload manager application service."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.upload_manager.models import UploadJob, UploadSession, UploadStage
from backend.upload_manager.pipeline import UploadPipeline
from backend.upload_manager.progress import UploadProgressService
from backend.upload_manager.queue import UploadQueue
from backend.upload_manager.repository import UploadRepository


class UploadManagerService:
    """Coordinate upload sessions, jobs, and progress metadata."""

    def __init__(
        self,
        *,
        repository: UploadRepository,
        queue: UploadQueue,
        pipeline: UploadPipeline,
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._pipeline = pipeline
        self._progress = UploadProgressService(repository)

    def create_session(
        self,
        *,
        project_id: str,
        source_id: str,
        total_files: int = 0,
        metadata: dict[str, object] | None = None,
    ) -> UploadSession:
        session = UploadSession(
            project_id=project_id,
            source_id=source_id,
            total_files=total_files,
            metadata=metadata or {},
            status="ready" if total_files == 0 else "queued",
        )
        return self._repository.create_session(session)

    def get_session(self, session_id: str) -> UploadSession | None:
        return self._repository.get_session(session_id)

    def get_jobs(self, session_id: str) -> list[UploadJob]:
        return self._repository.list_jobs(session_id)

    def enqueue_jobs(
        self, session_id: str, files: list[dict[str, object]]
    ) -> list[UploadJob]:
        session = self._require_session(session_id)
        created: list[UploadJob] = []
        for file_info in files:
            job = UploadJob(
                session_id=session.id,
                file_name=str(file_info.get("file_name", "file")),
                file_size=int(file_info.get("file_size", 0)),
                mime_type=str(file_info.get("mime_type", "application/octet-stream")),
                parser=str(file_info.get("parser", "auto")),
                status="queued",
            )
            stored = self._repository.create_job(job)
            self._queue.enqueue(stored)
            created.append(stored)

        session.total_files += len(created)
        session.status = "queued"
        session.current_file = created[0].file_name if created else session.current_file
        self._repository.update_session(session)
        return created

    def cancel_session(self, session_id: str) -> UploadSession:
        session = self._require_session(session_id)
        session.status = "cancelled"
        session.completed_at = datetime.now(UTC)
        for job in self._repository.list_jobs(session_id):
            if job.status not in {"completed", "failed"}:
                job.status = "cancelled"
                self._repository.update_job(job)
                self._queue.cancel(job.id)
        return self._repository.update_session(session)

    def resume_session(self, session_id: str) -> UploadSession:
        session = self._require_session(session_id)
        session.status = "queued"
        session.completed_at = None
        for job in self._repository.list_jobs(session_id):
            if job.status == "cancelled":
                job.status = "queued"
                self._repository.update_job(job)
                self._queue.resume(job.id)
        return self._repository.update_session(session)

    def process_job(self, job_id: str) -> UploadJob:
        job = self._repository.get_job(job_id)
        if job is None:
            raise KeyError(f"Upload job '{job_id}' not found")
        job.status = "processing"
        job.started_at = job.started_at or datetime.now(UTC)
        stages = self._pipeline.build(job)
        if UploadStage.FINISHED in stages:
            job.chunks_created = 0
            job.embeddings_created = 0
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
        return self._repository.update_job(job)

    def progress(self, session_id: str) -> dict[str, object]:
        return self._progress.get_progress(session_id)

    def summary(self, session_id: str) -> dict[str, object]:
        return self._progress.get_summary(session_id)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "sessions": len(self._progress._repository._sessions),
            "queued_jobs": len(self._queue._queue),
        }

    def _require_session(self, session_id: str) -> UploadSession:
        session = self._repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Upload session '{session_id}' not found")
        return session
