"""Agent Studio domain entity definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class Agent:
    """Represents a configurable Agent Studio agent."""

    id: str
    name: str
    description: str
    instructions: str
    system_prompt: str
    role: str
    goal: str
    expected_output: str
    temperature: float
    model: str
    enabled: bool
    color: str
    icon: str
    capabilities: list[str] = field(default_factory=list)
    agent_memory_enabled: bool = True
    project_memory_enabled: bool = True
    long_term_memory_enabled: bool = True
    conversation_memory_enabled: bool = True
    memory_importance: float = 0.5
    memory_scope: str = "project"
    knowledge_source_ids: list[str] = field(default_factory=list)
    document_library_ids: list[str] = field(default_factory=list)
    github_repositories: list[str] = field(default_factory=list)
    sharepoint_sites: list[str] = field(default_factory=list)
    uploaded_document_ids: list[str] = field(default_factory=list)
    project_knowledge_enabled: bool = True
    tools_allowed: list[str] = field(default_factory=list)
    tool_permissions: dict[str, bool] = field(default_factory=dict)
    connectors_allowed: list[str] = field(default_factory=list)
    execution_mode: str = "sequential"
    approval_required: bool = False
    max_iterations: int = 1
    timeout: int = 60
    retry_count: int = 0
    retry_policy: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    connected_agent_ids: list[str] = field(default_factory=list)
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
        instructions: str,
        system_prompt: str,
        role: str,
        goal: str,
        expected_output: str,
        temperature: float,
        model: str,
        enabled: bool = True,
        color: str = "#2563eb",
        icon: str = "sparkles",
        capabilities: list[str] | None = None,
        agent_memory_enabled: bool = True,
        project_memory_enabled: bool = True,
        long_term_memory_enabled: bool = True,
        conversation_memory_enabled: bool = True,
        memory_importance: float = 0.5,
        memory_scope: str = "project",
        knowledge_source_ids: list[str] | None = None,
        document_library_ids: list[str] | None = None,
        github_repositories: list[str] | None = None,
        sharepoint_sites: list[str] | None = None,
        uploaded_document_ids: list[str] | None = None,
        project_knowledge_enabled: bool = True,
        tools_allowed: list[str] | None = None,
        tool_permissions: dict[str, bool] | None = None,
        connectors_allowed: list[str] | None = None,
        execution_mode: str = "sequential",
        approval_required: bool = False,
        max_iterations: int = 1,
        timeout: int = 60,
        retry_count: int = 0,
        retry_policy: dict[str, object] | None = None,
        tags: list[str] | None = None,
        connected_agent_ids: list[str] | None = None,
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
            instructions=instructions,
            system_prompt=system_prompt,
            role=role,
            goal=goal,
            expected_output=expected_output,
            temperature=temperature,
            model=model,
            enabled=enabled,
            color=color,
            icon=icon,
            capabilities=list(capabilities or []),
            agent_memory_enabled=agent_memory_enabled,
            project_memory_enabled=project_memory_enabled,
            long_term_memory_enabled=long_term_memory_enabled,
            conversation_memory_enabled=conversation_memory_enabled,
            memory_importance=memory_importance,
            memory_scope=memory_scope,
            knowledge_source_ids=list(knowledge_source_ids or []),
            document_library_ids=list(document_library_ids or []),
            github_repositories=list(github_repositories or []),
            sharepoint_sites=list(sharepoint_sites or []),
            uploaded_document_ids=list(uploaded_document_ids or []),
            project_knowledge_enabled=project_knowledge_enabled,
            tools_allowed=list(tools_allowed or []),
            tool_permissions=dict(tool_permissions or {}),
            connectors_allowed=list(connectors_allowed or []),
            execution_mode=execution_mode,
            approval_required=approval_required,
            max_iterations=max_iterations,
            timeout=timeout,
            retry_count=retry_count,
            retry_policy=dict(retry_policy or {}),
            tags=list(tags or []),
            connected_agent_ids=list(connected_agent_ids or []),
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        """Refresh the modification timestamp."""
        self.updated_at = datetime.now(UTC)

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize the agent into a JSON-safe snapshot."""
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["updated_at"] = self.updated_at.isoformat()
        return payload

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "Agent":
        """Restore an agent from a JSON-safe snapshot."""
        payload = dict(snapshot)
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["updated_at"] = datetime.fromisoformat(str(payload["updated_at"]))
        payload["capabilities"] = list(payload.get("capabilities", []))
        payload["knowledge_source_ids"] = list(payload.get("knowledge_source_ids", []))
        payload["document_library_ids"] = list(payload.get("document_library_ids", []))
        payload["github_repositories"] = list(payload.get("github_repositories", []))
        payload["sharepoint_sites"] = list(payload.get("sharepoint_sites", []))
        payload["uploaded_document_ids"] = list(
            payload.get("uploaded_document_ids", [])
        )
        payload["tools_allowed"] = list(payload.get("tools_allowed", []))
        payload["tool_permissions"] = dict(payload.get("tool_permissions", {}))
        payload["connectors_allowed"] = list(payload.get("connectors_allowed", []))
        payload["retry_policy"] = dict(payload.get("retry_policy", {}))
        payload["tags"] = list(payload.get("tags", []))
        payload["connected_agent_ids"] = list(payload.get("connected_agent_ids", []))
        return cls(**payload)
