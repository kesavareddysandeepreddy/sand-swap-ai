"""Execution graph domain models and deterministic graph operations."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    """Lifecycle status for execution graph nodes."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class RetryPolicy:
    """Retry configuration for a graph node."""

    max_retries: int = 0
    backoff_seconds: float = 0.0
    exponential_backoff: bool = False

    def validate(self) -> list[str]:
        """Return validation errors for invalid retry configuration."""
        errors: list[str] = []
        if self.max_retries < 0:
            errors.append("max_retries must be >= 0")
        if self.backoff_seconds < 0:
            errors.append("backoff_seconds must be >= 0")
        return errors

    def as_metadata(self) -> dict[str, Any]:
        """Serialize retry policy deterministically."""
        return {
            "max_retries": self.max_retries,
            "backoff_seconds": self.backoff_seconds,
            "exponential_backoff": self.exponential_backoff,
        }


@dataclass(slots=True)
class ExecutionNode:
    """A node representing one executable unit in the execution graph."""

    node_id: str
    step_id: str
    order: int
    title: str
    action: str
    target: str
    capabilities: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    complexity: str = "low"
    status: NodeStatus = NodeStatus.PENDING
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, Any]:
        """Serialize node metadata deterministically."""
        return {
            "node_id": self.node_id,
            "step_id": self.step_id,
            "order": self.order,
            "title": self.title,
            "action": self.action,
            "target": self.target,
            "capabilities": list(self.capabilities),
            "estimated_cost": self.estimated_cost,
            "complexity": self.complexity,
            "status": self.status.value,
            "retry_policy": self.retry_policy.as_metadata(),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ExecutionEdge:
    """A directed dependency edge between two execution nodes."""

    predecessor_node_id: str
    successor_node_id: str
    reason: str = "depends_on"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, Any]:
        """Serialize edge metadata deterministically."""
        return {
            "predecessor_node_id": self.predecessor_node_id,
            "successor_node_id": self.successor_node_id,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ExecutionGraph:
    """Directed acyclic graph for deterministic execution planning."""

    nodes: list[ExecutionNode] = field(default_factory=list)
    edges: list[ExecutionEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> ExecutionNode | None:
        """Return one node by node identifier."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_node_by_step_id(self, step_id: str) -> ExecutionNode | None:
        """Return one node by originating task step identifier."""
        for node in self.nodes:
            if node.step_id == step_id:
                return node
        return None

    def dependencies_of(self, node_id: str) -> list[ExecutionNode]:
        """Return predecessor nodes required before this node can execute."""
        predecessor_ids = [
            edge.predecessor_node_id
            for edge in self.edges
            if edge.successor_node_id == node_id
        ]
        predecessors = [self.get_node(item) for item in predecessor_ids]
        return [item for item in predecessors if item is not None]

    def dependents_of(self, node_id: str) -> list[ExecutionNode]:
        """Return successor nodes that depend on this node."""
        successor_ids = [
            edge.successor_node_id
            for edge in self.edges
            if edge.predecessor_node_id == node_id
        ]
        successors = [self.get_node(item) for item in successor_ids]
        return [item for item in successors if item is not None]

    def topological_order(self) -> list[ExecutionNode]:
        """Return deterministic topological ordering using Kahn's algorithm."""
        node_ids = [node.node_id for node in self.nodes]
        in_degree = {node_id: 0 for node_id in node_ids}
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

        for edge in self.edges:
            if edge.predecessor_node_id in adjacency:
                adjacency[edge.predecessor_node_id].append(edge.successor_node_id)
            if edge.successor_node_id in in_degree:
                in_degree[edge.successor_node_id] += 1

        ordered_by_stability = sorted(
            self.nodes,
            key=lambda item: (item.order, item.node_id),
        )
        queue: deque[str] = deque(
            [
                node.node_id
                for node in ordered_by_stability
                if in_degree[node.node_id] == 0
            ]
        )

        ordered_ids: list[str] = []
        while queue:
            current = queue.popleft()
            ordered_ids.append(current)
            for successor in sorted(adjacency.get(current, [])):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if len(ordered_ids) != len(node_ids):
            raise ValueError("Execution graph contains a cycle.")

        node_lookup = {node.node_id: node for node in self.nodes}
        return [node_lookup[node_id] for node_id in ordered_ids]

    def has_cycle(self) -> bool:
        """Return whether the graph contains a cycle."""
        try:
            _ = self.topological_order()
            return False
        except ValueError:
            return True

    def validate(self) -> list[str]:
        """Return deterministic validation errors for graph integrity."""
        errors: list[str] = []

        if not self.nodes:
            errors.append("ExecutionGraph must contain at least one node")

        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("ExecutionGraph contains duplicate node_id values")

        step_ids = [node.step_id for node in self.nodes]
        if len(step_ids) != len(set(step_ids)):
            errors.append("ExecutionGraph contains duplicate step_id values")

        node_lookup = {node.node_id: node for node in self.nodes}
        for edge in self.edges:
            if edge.predecessor_node_id not in node_lookup:
                errors.append(
                    f"Edge references unknown predecessor node: {edge.predecessor_node_id}"
                )
            if edge.successor_node_id not in node_lookup:
                errors.append(
                    f"Edge references unknown successor node: {edge.successor_node_id}"
                )
            if edge.predecessor_node_id == edge.successor_node_id:
                errors.append(
                    f"Self dependency detected for node: {edge.predecessor_node_id}"
                )

        for node in self.nodes:
            if not node.node_id:
                errors.append("ExecutionNode.node_id cannot be empty")
            if not node.step_id:
                errors.append("ExecutionNode.step_id cannot be empty")
            if node.order <= 0:
                errors.append(
                    f"ExecutionNode.order must be > 0 for node {node.node_id}"
                )
            if node.estimated_cost < 0:
                errors.append(
                    f"ExecutionNode.estimated_cost must be >= 0 for node {node.node_id}"
                )
            errors.extend(node.retry_policy.validate())

        if not errors and self.has_cycle():
            errors.append("ExecutionGraph contains a cycle")

        return sorted(set(errors))

    def as_metadata(self) -> dict[str, Any]:
        """Serialize graph metadata deterministically."""
        nodes = sorted(self.nodes, key=lambda item: (item.order, item.node_id))
        edges = sorted(
            self.edges,
            key=lambda item: (
                item.predecessor_node_id,
                item.successor_node_id,
                item.reason,
            ),
        )

        return {
            "nodes": [node.as_metadata() for node in nodes],
            "edges": [edge.as_metadata() for edge in edges],
            "metadata": dict(self.metadata),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }
