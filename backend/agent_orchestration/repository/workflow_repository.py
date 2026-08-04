"""Repository contract for workflow orchestration persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.agent_orchestration.domain.run import WorkflowRun
from backend.agent_orchestration.domain.workflow import Workflow


class WorkflowRepository(ABC):
    """Persistence contract for workflows, versions, and executions."""

    @abstractmethod
    def create_workflow(self, workflow: Workflow) -> Workflow:
        """Persist a new workflow."""

    @abstractmethod
    def update_workflow(self, workflow: Workflow) -> Workflow:
        """Persist workflow updates."""

    @abstractmethod
    def delete_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        """Delete workflow in ownership scope."""

    @abstractmethod
    def get_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Workflow | None:
        """Return one workflow in ownership scope."""

    @abstractmethod
    def list_workflows(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Workflow]:
        """List workflows in ownership scope."""

    @abstractmethod
    def list_workflow_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        """List workflow version snapshots."""

    @abstractmethod
    def create_workflow_version(
        self,
        workflow_id: str,
        *,
        version_number: int,
        change_summary: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Persist one workflow snapshot."""

    @abstractmethod
    def get_latest_workflow_version_number(self, workflow_id: str) -> int:
        """Return latest version number for workflow."""

    @abstractmethod
    def create_run(self, run: WorkflowRun) -> WorkflowRun:
        """Persist a new workflow run."""

    @abstractmethod
    def update_run(self, run: WorkflowRun) -> WorkflowRun:
        """Persist workflow run updates."""

    @abstractmethod
    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Return one run by id."""

    @abstractmethod
    def list_runs(self, workflow_id: str) -> list[WorkflowRun]:
        """List runs for one workflow."""

    @abstractmethod
    def list_recent_runs(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        limit: int,
    ) -> list[WorkflowRun]:
        """List recent runs in ownership scope."""

    @abstractmethod
    def dashboard_metrics(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Compute dashboard metrics for orchestration workflows."""

    @abstractmethod
    def create_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        """Persist one autonomous mission record."""

    @abstractmethod
    def update_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        """Persist updates for an autonomous mission record."""

    @abstractmethod
    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        """Fetch one mission by identifier."""

    @abstractmethod
    def list_missions(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """List recent missions in ownership scope."""

    @abstractmethod
    def create_mission_template(self, template: dict[str, Any]) -> dict[str, Any]:
        """Persist one reusable mission template."""

    @abstractmethod
    def update_mission_template(self, template: dict[str, Any]) -> dict[str, Any]:
        """Persist updates for one mission template."""

    @abstractmethod
    def list_mission_templates(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """List mission templates in ownership scope."""

    @abstractmethod
    def get_mission_template(self, template_id: str) -> dict[str, Any] | None:
        """Fetch one mission template by identifier."""
