"""Repository contract for Agent Studio agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.agent_studio.domain.entities.agent import Agent
from backend.agent_studio.domain.entities.agent_test_run import AgentTestRun
from backend.agent_studio.domain.entities.agent_version import AgentVersion


class AgentRepository(ABC):
    """Persistence contract for Agent Studio agents."""

    @abstractmethod
    def create(self, agent: Agent) -> Agent:
        """Create a new agent record."""

    @abstractmethod
    def update(self, agent: Agent) -> Agent:
        """Persist an existing agent record."""

    @abstractmethod
    def delete(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> bool:
        """Delete one agent in the given ownership scope."""

    @abstractmethod
    def get_by_id(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent | None:
        """Fetch one agent within the requested ownership scope."""

    @abstractmethod
    def list_by_scope(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Agent]:
        """List agents for one ownership scope."""

    @abstractmethod
    def enable(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> Agent:
        """Enable an agent in scope."""

    @abstractmethod
    def disable(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> Agent:
        """Disable an agent in scope."""

    @abstractmethod
    def list_versions(self, agent_id: str) -> list[AgentVersion]:
        """Return stored versions for an agent."""

    @abstractmethod
    def get_version(self, version_id: str) -> AgentVersion | None:
        """Return one stored agent version."""

    @abstractmethod
    def get_latest_version_number(self, agent_id: str) -> int:
        """Return the latest version number for an agent."""

    @abstractmethod
    def create_version(self, version: AgentVersion) -> AgentVersion:
        """Persist one version snapshot."""

    @abstractmethod
    def list_test_runs(self, agent_id: str) -> list[AgentTestRun]:
        """Return stored test runs for an agent."""

    @abstractmethod
    def get_test_run(self, test_run_id: str) -> AgentTestRun | None:
        """Return one stored test run."""

    @abstractmethod
    def create_test_run(self, test_run: AgentTestRun) -> AgentTestRun:
        """Persist one test run."""

    @abstractmethod
    def dashboard_metrics(self, agent_id: str) -> dict[str, Any]:
        """Return dashboard metrics derived from stored runs and versions."""
