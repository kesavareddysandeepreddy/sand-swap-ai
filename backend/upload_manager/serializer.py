"""Serialization helpers for upload manager models."""

from __future__ import annotations

from backend.upload_manager.models import UploadJob, UploadSession


def serialize_session(session: UploadSession) -> dict[str, object]:
    return {
        "id": session.id,
        "project_id": session.project_id,
        "source_id": session.source_id,
        "status": session.status,
        "total_files": session.total_files,
        "processed_files": session.processed_files,
        "failed_files": session.failed_files,
        "skipped_files": session.skipped_files,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "current_file": session.current_file,
        "metadata": session.metadata,
    }


def serialize_job(job: UploadJob) -> dict[str, object]:
    return {
        "id": job.id,
        "session_id": job.session_id,
        "file_name": job.file_name,
        "file_size": job.file_size,
        "mime_type": job.mime_type,
        "parser": job.parser,
        "status": job.status,
        "chunks_created": job.chunks_created,
        "embeddings_created": job.embeddings_created,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error": job.error,
    }
