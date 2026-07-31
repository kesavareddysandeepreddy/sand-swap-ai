"""Application service for Agent Studio agent lifecycle operations."""

from __future__ import annotations

from uuid import uuid4

from backend.agent_studio.domain.entities.agent import Agent
from backend.agent_studio.models.agent import AgentCreateRequest, AgentUpdateRequest
from backend.agent_studio.repository.agent_repository import AgentRepository
from backend.core.logging.logger import LoggerFactory

logger = LoggerFactory.get_logger("AgentStudioService")


class AgentService:
    """Orchestrates Agent Studio CRUD and enablement operations."""

    def __init__(self, *, repository: AgentRepository) -> None:
        self._repository = repository

    def create_agent(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AgentCreateRequest,
    ) -> Agent:
        """Create and persist a new agent."""
        agent = Agent.create(
            agent_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            role=payload.role,
            objective=payload.objective,
            system_prompt=payload.system_prompt,
            enabled=payload.enabled,
            short_term_enabled=payload.short_term_enabled,
            long_term_enabled=payload.long_term_enabled,
            project_memory_enabled=payload.project_memory_enabled,
            tools_allowed=list(payload.tools_allowed),
            connectors_allowed=list(payload.connectors_allowed),
            approval_required=payload.approval_required,
            max_iterations=payload.max_iterations,
            timeout=payload.timeout,
            retry_policy=dict(payload.retry_policy),
            tags=list(payload.tags),
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        stored = self._repository.create(agent)
        logger.debug(
            "AGENT_CREATED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            stored.id,
            stored.owner_id,
            stored.workspace_id,
            stored.project_id,
        )
        return stored

    def list_agents(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Agent]:
        """List agents in scope."""
        return self._repository.list_by_scope(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def get_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent | None:
        """Fetch one agent in scope."""
        return self._repository.get_by_id(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def update_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AgentUpdateRequest,
    ) -> Agent:
        """Apply a partial update to an agent."""
        current = self._require_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        updated = current
        data = payload.model_dump(exclude_unset=True)
        for field_name, value in data.items():
            if value is not None:
                setattr(updated, field_name, value)
        updated.touch()
        stored = self._repository.update(updated)
        logger.debug(
            "AGENT_UPDATED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            stored.id,
            stored.owner_id,
            stored.workspace_id,
            stored.project_id,
        )
        return stored

    def delete_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        """Delete an agent in scope."""
        deleted = self._repository.delete(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if deleted:
            logger.debug(
                "AGENT_DELETED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
                agent_id,
                owner_id,
                workspace_id,
                project_id,
            )
        return deleted

    def enable_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        """Enable an agent."""
        agent = self._repository.enable(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        logger.debug(
            "AGENT_ENABLED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            agent.id,
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
        )
        return agent

    def disable_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        """Disable an agent."""
        agent = self._repository.disable(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        logger.debug(
            "AGENT_DISABLED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            agent.id,
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
        )
        return agent

    def _require_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        agent = self.get_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")
        return agent
