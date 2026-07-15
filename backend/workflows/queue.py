"""In-memory workflow queue.

This implementation is intentionally simple and replaceable by
Celery/Redis-backed queues in future sprints.
"""

from __future__ import annotations

from collections import deque

from backend.workflows.models import Workflow


class InMemoryWorkflowQueue:
    """FIFO queue for workflow scheduling."""

    def __init__(self) -> None:
        self._items: deque[Workflow] = deque()

    def enqueue(self, workflow: Workflow) -> None:
        """Push a workflow to the queue tail."""
        self._items.append(workflow)

    def dequeue(self) -> Workflow | None:
        """Pop the next workflow from the queue head."""
        if not self._items:
            return None
        return self._items.popleft()

    def peek(self) -> Workflow | None:
        """Return the next workflow without dequeuing it."""
        if not self._items:
            return None
        return self._items[0]

    def size(self) -> int:
        """Return number of queued workflows."""
        return len(self._items)

    def is_empty(self) -> bool:
        """Return True when queue has no items."""
        return not self._items

    def clear(self) -> None:
        """Remove all queued workflows."""
        self._items.clear()
