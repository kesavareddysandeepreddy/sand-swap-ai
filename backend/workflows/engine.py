"""Workflow engine orchestration layer."""

from __future__ import annotations

from backend.workflows.context import WorkflowContext
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.models import Workflow, WorkflowResult
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry


class WorkflowEngine:
    """Queue-backed workflow execution engine."""

    def __init__(
        self,
        *,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor,
        queue: InMemoryWorkflowQueue,
    ) -> None:
        self.registry = registry
        self.executor = executor
        self.queue = queue

    def execute(self, workflow: Workflow, context: WorkflowContext) -> WorkflowResult:
        """Enqueue and execute a workflow immediately."""
        self.queue.enqueue(workflow)
        next_workflow = self.queue.dequeue()
        if next_workflow is None:
            raise RuntimeError("Workflow queue returned no item after enqueue.")
        return self.executor.execute(next_workflow, context)

    def execute_registered(
        self,
        workflow_type: str,
        *,
        context: WorkflowContext,
        **kwargs: object,
    ) -> WorkflowResult:
        """Create a workflow from registry and execute it."""
        workflow = self.registry.create(workflow_type, **kwargs)
        return self.execute(workflow=workflow, context=context)

    def health(self) -> dict[str, object]:
        """Return workflow engine health details."""
        return {
            "status": "ok",
            "queue_size": self.queue.size(),
            "registry": self.registry.health(),
        }
