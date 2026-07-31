"""FIFO queue for upload jobs."""

from __future__ import annotations

from collections import deque

from backend.upload_manager.models import UploadJob


class UploadQueue:
    """Simple in-memory FIFO queue for upload jobs."""

    def __init__(self) -> None:
        self._queue: deque[UploadJob] = deque()
        self._cancelled: set[str] = set()
        self._paused: set[str] = set()

    def enqueue(self, job: UploadJob) -> UploadJob:
        self._queue.append(job)
        return job

    def dequeue(self) -> UploadJob | None:
        while self._queue:
            job = self._queue.popleft()
            if job.id in self._cancelled or job.id in self._paused:
                continue
            return job
        return None

    def cancel(self, job_id: str) -> bool:
        self._cancelled.add(job_id)
        return True

    def resume(self, job_id: str) -> bool:
        was_cancelled = job_id in self._cancelled
        self._cancelled.discard(job_id)
        self._paused.discard(job_id)
        return was_cancelled

    def pause(self, job_id: str) -> bool:
        self._paused.add(job_id)
        return True
