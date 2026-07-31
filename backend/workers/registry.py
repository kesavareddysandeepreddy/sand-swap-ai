"""Worker registry for runtime worker discovery."""

from __future__ import annotations

from backend.workers.base_worker import BaseWorker


class WorkerRegistry:
    """Register and resolve available workers."""

    def __init__(self) -> None:
        self._workers: dict[str, BaseWorker] = {}

    def register(self, worker: BaseWorker) -> None:
        self._workers[worker.name()] = worker

    def discover(self) -> list[BaseWorker]:
        return [self._workers[name] for name in sorted(self._workers.keys())]

    def lookup(self, worker_name: str) -> BaseWorker | None:
        return self._workers.get(worker_name)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "workers": [worker.name() for worker in self.discover()],
        }
