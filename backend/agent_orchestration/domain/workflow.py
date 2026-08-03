"""Workflow domain entities for multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class NodeType(StrEnum):
    """Supported workflow node kinds."""

    START = "Start"
    AGENT = "Agent"
    CONDITION = "Condition"
    HUMAN_APPROVAL = "Human Approval"
    MERGE = "Merge"
    PARALLEL_SPLIT = "Parallel Split"
    LOOP = "Loop"
    END = "End"
    WEBHOOK = "Webhook"
    REST = "REST"
    EMAIL = "Email"
    SCHEDULER = "Scheduler"


@dataclass(slots=True)
class WorkflowNode:
    """Node configuration inside a workflow graph."""

    id: str
    node_type: str
    name: str
    agent_id: str | None = None
    x: float = 0.0
    y: float = 0.0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowEdge:
    """Directed edge connecting two workflow nodes."""

    id: str
    source_node_id: str
    target_node_id: str
    label: str = ""
    condition: str = ""


@dataclass(slots=True)
class Workflow:
    """Persisted orchestration workflow definition."""

    id: str
    name: str
    description: str
    enabled: bool
    owner_id: str
    workspace_id: str
    project_id: str
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    execution_settings: dict[str, Any] = field(default_factory=dict)
    shared_memory_settings: dict[str, Any] = field(default_factory=dict)
    approval_settings: dict[str, Any] = field(default_factory=dict)
    retry_settings: dict[str, Any] = field(default_factory=dict)
    timeout_settings: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str,
        enabled: bool,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        nodes: list[WorkflowNode] | None = None,
        edges: list[WorkflowEdge] | None = None,
        execution_settings: dict[str, Any] | None = None,
        shared_memory_settings: dict[str, Any] | None = None,
        approval_settings: dict[str, Any] | None = None,
        retry_settings: dict[str, Any] | None = None,
        timeout_settings: dict[str, Any] | None = None,
    ) -> "Workflow":
        """Build a new workflow aggregate."""
        return cls(
            id=str(uuid4()),
            name=name,
            description=description,
            enabled=enabled,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            nodes=list(nodes or []),
            edges=list(edges or []),
            execution_settings=dict(execution_settings or {}),
            shared_memory_settings=dict(shared_memory_settings or {}),
            approval_settings=dict(approval_settings or {}),
            retry_settings=dict(retry_settings or {}),
            timeout_settings=dict(timeout_settings or {}),
        )

    def touch(self) -> None:
        """Update modification timestamp."""
        self.updated_at = datetime.now(UTC)

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize workflow definition for versioning."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "owner_id": self.owner_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "nodes": [
                {
                    "id": node.id,
                    "node_type": node.node_type,
                    "name": node.name,
                    "agent_id": node.agent_id,
                    "x": node.x,
                    "y": node.y,
                    "config": dict(node.config),
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "label": edge.label,
                    "condition": edge.condition,
                }
                for edge in self.edges
            ],
            "execution_settings": dict(self.execution_settings),
            "shared_memory_settings": dict(self.shared_memory_settings),
            "approval_settings": dict(self.approval_settings),
            "retry_settings": dict(self.retry_settings),
            "timeout_settings": dict(self.timeout_settings),
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_snapshot(cls, payload: dict[str, Any]) -> "Workflow":
        """Hydrate workflow definition from repository snapshot."""
        nodes = [
            WorkflowNode(
                id=str(item.get("id", "")),
                node_type=str(item.get("node_type", "")),
                name=str(item.get("name", "")),
                agent_id=(
                    None
                    if item.get("agent_id") in {None, ""}
                    else str(item.get("agent_id"))
                ),
                x=float(item.get("x", 0.0)),
                y=float(item.get("y", 0.0)),
                config=dict(item.get("config", {})),
            )
            for item in list(payload.get("nodes", []))
            if isinstance(item, dict)
        ]
        edges = [
            WorkflowEdge(
                id=str(item.get("id", "")),
                source_node_id=str(item.get("source_node_id", "")),
                target_node_id=str(item.get("target_node_id", "")),
                label=str(item.get("label", "")),
                condition=str(item.get("condition", "")),
            )
            for item in list(payload.get("edges", []))
            if isinstance(item, dict)
        ]
        return cls(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            enabled=bool(payload.get("enabled", True)),
            owner_id=str(payload.get("owner_id", "anonymous")),
            workspace_id=str(payload.get("workspace_id", "default")),
            project_id=str(payload.get("project_id", "default")),
            nodes=nodes,
            edges=edges,
            execution_settings=dict(payload.get("execution_settings", {})),
            shared_memory_settings=dict(payload.get("shared_memory_settings", {})),
            approval_settings=dict(payload.get("approval_settings", {})),
            retry_settings=dict(payload.get("retry_settings", {})),
            timeout_settings=dict(payload.get("timeout_settings", {})),
            version=int(payload.get("version", 1)),
            created_at=datetime.fromisoformat(str(payload.get("created_at"))),
            updated_at=datetime.fromisoformat(str(payload.get("updated_at"))),
        )
