"""Agent Studio domain entity definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Agent:
    """Represents a configurable Agent Studio agent."""

    id: str
    name: str
    description: str
    role: str
    objective: str
    system_prompt: str
    enabled: bool
    short_term_enabled: bool
    long_term_enabled: bool
    project_memory_enabled: bool
    tools_allowed: list[str] = field(default_factory=list)
    connectors_allowed: list[str] = field(default_factory=list)
    approval_required: bool = False
    max_iterations: int = 1
    timeout: int = 60
    retry_policy: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    owner_id: str = "anonymous"
    workspace_id: str = "default"
    project_id: str = "default"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        name: str,
        description: str,
        role: str,
        objective: str,
        system_prompt: str,
        enabled: bool = True,
        short_term_enabled: bool = True,
        long_term_enabled: bool = True,
        project_memory_enabled: bool = True,
        tools_allowed: list[str] | None = None,
        connectors_allowed: list[str] | None = None,
        approval_required: bool = False,
        max_iterations: int = 1,
        timeout: int = 60,
        retry_policy: dict[str, object] | None = None,
        tags: list[str] | None = None,
        owner_id: str = "anonymous",
        workspace_id: str = "default",
        project_id: str = "default",
    ) -> "Agent":
        """Construct a new agent with normalized defaults."""
        now = datetime.now(UTC)
        return cls(
            id=agent_id,
            name=name,
            description=description,
            role=role,
            objective=objective,
            system_prompt=system_prompt,
            enabled=enabled,
            short_term_enabled=short_term_enabled,
            long_term_enabled=long_term_enabled,
            project_memory_enabled=project_memory_enabled,
            tools_allowed=list(tools_allowed or []),
            connectors_allowed=list(connectors_allowed or []),
            approval_required=approval_required,
            max_iterations=max_iterations,
            timeout=timeout,
            retry_policy=dict(retry_policy or {}),
            tags=list(tags or []),
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        """Refresh the modification timestamp."""
        self.updated_at = datetime.now(UTC)
