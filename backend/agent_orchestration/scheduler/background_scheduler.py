"""Background execution scheduler for workflow runs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from typing import Callable


class BackgroundWorkflowScheduler:
    """Executes workflow runs asynchronously on a bounded thread pool."""

    def __init__(self, *, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="workflow-run"
        )
        self._lock = RLock()
        self._futures: dict[str, Future[None]] = {}

    def submit(self, run_id: str, callback: Callable[[], None]) -> None:
        """Schedule one workflow run callback."""
        with self._lock:
            future = self._executor.submit(callback)
            self._futures[run_id] = future

    def status(self, run_id: str) -> str:
        """Return scheduler-level status for one run."""
        with self._lock:
            future = self._futures.get(run_id)
            if future is None:
                return "not_found"
            if future.running():
                return "running"
            if future.done():
                return "done"
            return "queued"

    def close(self) -> None:
        """Shutdown scheduler resources."""
        self._executor.shutdown(wait=False, cancel_futures=True)
