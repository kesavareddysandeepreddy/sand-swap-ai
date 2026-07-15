"""Registry for workflow type factories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.workflows.models import Workflow

WorkflowFactory = Callable[..., Workflow]


class WorkflowRegistry:
    """Register and create workflow types."""

    def __init__(self) -> None:
        self._factories: dict[str, WorkflowFactory] = {}

    def register(self, workflow_type: str, factory: WorkflowFactory) -> None:
        """Register a workflow type factory."""
        normalized = workflow_type.strip()
        if not normalized:
            raise ValueError("Workflow type cannot be empty.")
        self._factories[normalized] = factory

    def discover(self) -> list[str]:
        """List known workflow types."""
        return sorted(self._factories.keys())

    def lookup(self, workflow_type: str) -> WorkflowFactory | None:
        """Resolve workflow factory by type."""
        return self._factories.get(workflow_type)

    def create(self, workflow_type: str, **kwargs: Any) -> Workflow:
        """Build a workflow from a registered type."""
        factory = self.lookup(workflow_type)
        if factory is None:
            raise KeyError(f"Unknown workflow type: {workflow_type}")
        return factory(**kwargs)

    def health(self) -> dict[str, object]:
        """Return registry health details."""
        return {
            "status": "ok",
            "registered_types": self.discover(),
        }
