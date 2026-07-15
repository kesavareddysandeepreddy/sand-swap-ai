"""Sequential workflow executor with retry/cancel/failure handling."""

from __future__ import annotations

import time
from collections.abc import Callable

from backend.core.logging.logger import LoggerFactory
from backend.workflows.context import WorkflowContext
from backend.workflows.models import (
    Workflow,
    WorkflowResult,
    WorkflowTask,
    WorkflowTaskResult,
)
from backend.workflows.task import AgentResponseTask, Task, ToolRouterTask

TaskFactory = Callable[[WorkflowTask], Task]


class WorkflowExecutor:
    """Execute workflow tasks in order with retries and rollback."""

    def __init__(self, task_factory: TaskFactory | None = None) -> None:
        self._task_factory = task_factory or self._default_task_factory
        self.logger = LoggerFactory.get_logger("WorkflowExecutor")

    def _default_task_factory(self, definition: WorkflowTask) -> Task:
        task_kind = str(definition.metadata.get("task_kind", "tool_router"))
        if task_kind == "agent_response":
            return AgentResponseTask(definition)
        return ToolRouterTask(definition)

    def _rollback_executed_tasks(
        self,
        executed_tasks: list[Task],
        context: WorkflowContext,
        workflow_id: str,
    ) -> None:
        for task in reversed(executed_tasks):
            try:
                task.rollback(context)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception(
                    "Rollback failed workflow_id=%s task=%s error=%s",
                    workflow_id,
                    task.definition.name,
                    exc,
                )

    def execute(self, workflow: Workflow, context: WorkflowContext) -> WorkflowResult:
        """Run workflow tasks sequentially and return execution result."""
        started_at = time.perf_counter()
        self.logger.info(
            "Workflow started workflow_id=%s workflow_type=%s task_count=%d",
            workflow.workflow_id,
            workflow.workflow_type,
            len(workflow.tasks),
        )

        task_results: list[WorkflowTaskResult] = []
        executed_tasks: list[Task] = []
        response_text = ""

        for definition in workflow.tasks:
            if context.is_cancelled():
                elapsed = time.perf_counter() - started_at
                self.logger.info(
                    "Workflow cancelled workflow_id=%s execution_time=%.6f",
                    workflow.workflow_id,
                    elapsed,
                )
                self._rollback_executed_tasks(
                    executed_tasks, context, workflow.workflow_id
                )
                return WorkflowResult(
                    workflow_id=workflow.workflow_id,
                    workflow_type=workflow.workflow_type,
                    selected_agent=workflow.selected_agent,
                    status="cancelled",
                    task_results=task_results,
                    response_text=response_text,
                    execution_time=elapsed,
                    metadata={"cancelled": True},
                )

            task = self._task_factory(definition)
            attempts = 0
            max_attempts = max(1, definition.max_retries + 1)

            while attempts < max_attempts:
                attempts += 1
                self.logger.info(
                    "Task started workflow_id=%s task=%s attempt=%d",
                    workflow.workflow_id,
                    definition.name,
                    attempts,
                )
                try:
                    output = task.execute(context)
                    self.logger.info(
                        "Task completed workflow_id=%s task=%s",
                        workflow.workflow_id,
                        definition.name,
                    )
                    task_results.append(
                        WorkflowTaskResult(
                            task_id=definition.task_id,
                            task_name=definition.name,
                            status="completed",
                            attempts=attempts,
                            output=output,
                        )
                    )
                    executed_tasks.append(task)
                    if "response_text" in output:
                        response_text = str(output["response_text"])
                    break
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception(
                        "Task failed workflow_id=%s task=%s error=%s",
                        workflow.workflow_id,
                        definition.name,
                        exc,
                    )
                    if attempts < max_attempts:
                        self.logger.warning(
                            "Retry workflow_id=%s task=%s attempt=%d",
                            workflow.workflow_id,
                            definition.name,
                            attempts,
                        )
                        continue

                    task_results.append(
                        WorkflowTaskResult(
                            task_id=definition.task_id,
                            task_name=definition.name,
                            status="failed",
                            attempts=attempts,
                            error=str(exc),
                        )
                    )
                    self._rollback_executed_tasks(
                        executed_tasks,
                        context,
                        workflow.workflow_id,
                    )
                    elapsed = time.perf_counter() - started_at
                    self.logger.info(
                        "Workflow failed workflow_id=%s execution_time=%.6f",
                        workflow.workflow_id,
                        elapsed,
                    )
                    return WorkflowResult(
                        workflow_id=workflow.workflow_id,
                        workflow_type=workflow.workflow_type,
                        selected_agent=workflow.selected_agent,
                        status="failed",
                        task_results=task_results,
                        response_text=response_text,
                        execution_time=elapsed,
                        metadata={"failed_task": definition.name},
                    )

        elapsed = time.perf_counter() - started_at
        self.logger.info(
            "Workflow completed workflow_id=%s execution_time=%.6f",
            workflow.workflow_id,
            elapsed,
        )
        return WorkflowResult(
            workflow_id=workflow.workflow_id,
            workflow_type=workflow.workflow_type,
            selected_agent=workflow.selected_agent,
            status="completed",
            task_results=task_results,
            response_text=response_text,
            execution_time=elapsed,
            metadata={"completed_task_count": len(task_results)},
        )
