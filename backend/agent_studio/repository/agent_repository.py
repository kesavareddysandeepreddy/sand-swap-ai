"""Repository contract for Agent Studio agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.agent_studio.domain.entities.agent import Agent


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
