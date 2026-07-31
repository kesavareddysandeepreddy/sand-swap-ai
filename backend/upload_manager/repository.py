"""In-memory repository for upload sessions and jobs."""

from __future__ import annotations

from copy import deepcopy

from backend.upload_manager.models import UploadJob, UploadSession


class UploadRepository:
    """Persist upload sessions and jobs in memory."""

    def __init__(self) -> None:
        self._sessions: dict[str, UploadSession] = {}
        self._jobs: dict[str, UploadJob] = {}

    def create_session(self, session: UploadSession) -> UploadSession:
        stored = deepcopy(session)
        self._sessions[stored.id] = stored
        return deepcopy(stored)

    def get_session(self, session_id: str) -> UploadSession | None:
        session = self._sessions.get(session_id)
        return deepcopy(session) if session is not None else None

    def update_session(self, session: UploadSession) -> UploadSession:
        if session.id not in self._sessions:
            raise KeyError(f"Upload session '{session.id}' not found")
        self._sessions[session.id] = deepcopy(session)
        return deepcopy(self._sessions[session.id])

    def create_job(self, job: UploadJob) -> UploadJob:
        stored = deepcopy(job)
        self._jobs[stored.id] = stored
        return deepcopy(stored)

    def update_job(self, job: UploadJob) -> UploadJob:
        if job.id not in self._jobs:
            raise KeyError(f"Upload job '{job.id}' not found")
        self._jobs[job.id] = deepcopy(job)
        return deepcopy(self._jobs[job.id])

    def list_jobs(self, session_id: str) -> list[UploadJob]:
        return [
            deepcopy(job) for job in self._jobs.values() if job.session_id == session_id
        ]

    def get_job(self, job_id: str) -> UploadJob | None:
        job = self._jobs.get(job_id)
        return deepcopy(job) if job is not None else None
