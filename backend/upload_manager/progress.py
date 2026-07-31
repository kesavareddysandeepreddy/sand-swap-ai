"""Progress calculations for upload sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.upload_manager.models import UploadSession
from backend.upload_manager.repository import UploadRepository


class UploadProgressService:
    """Compute progress and ETA data for upload sessions."""

    def __init__(self, repository: UploadRepository) -> None:
        self._repository = repository

    def get_progress(self, session_id: str) -> dict[str, object]:
        session = self._require_session(session_id)
        remaining = max(0, session.total_files - session.processed_files)
        percent = 0.0
        if session.total_files > 0:
            percent = round((session.processed_files / session.total_files) * 100.0, 2)
        return {
            "session_id": session.id,
            "status": session.status,
            "total_files": session.total_files,
            "processed_files": session.processed_files,
            "remaining_files": remaining,
            "failed_files": session.failed_files,
            "skipped_files": session.skipped_files,
            "progress_percent": percent,
            "current_file": session.current_file,
            "eta": self.calculate_eta(session_id),
        }

    def get_summary(self, session_id: str) -> dict[str, object]:
        session = self._require_session(session_id)
        return {
            "session_id": session.id,
            "status": session.status,
            "processed_files": session.processed_files,
            "remaining_files": max(0, session.total_files - session.processed_files),
            "failed_files": session.failed_files,
            "skipped_files": session.skipped_files,
            "current_file": session.current_file,
        }

    def calculate_eta(self, session_id: str) -> str | None:
        session = self._require_session(session_id)
        if session.total_files <= 0 or session.processed_files <= 0:
            return None
        elapsed = datetime.now(UTC) - session.started_at
        avg_per_file = elapsed / max(1, session.processed_files)
        remaining = max(0, session.total_files - session.processed_files)
        eta = datetime.now(UTC) + (avg_per_file * remaining)
        return eta.isoformat()

    def _require_session(self, session_id: str) -> UploadSession:
        session = self._repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Upload session '{session_id}' not found")
        return session
