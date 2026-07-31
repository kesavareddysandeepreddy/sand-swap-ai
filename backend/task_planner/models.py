"""Deterministic task-planning models for autonomous execution preparation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CapabilityName = Literal[
    "filesystem",
    "document",
    "memory",
    "rag",
    "vision",
    "mcp",
    "python",
    "rest",
    "workflow",
]

TaskComplexity = Literal["low", "medium", "high"]


@dataclass(slots=True)
class TaskGoal:
    """Parsed user goal extracted from request text."""

    original_request: str
    actions: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskDependency:
    """Directed dependency edge between two planned steps."""

    predecessor_step_id: str
    successor_step_id: str
    reason: str


@dataclass(slots=True)
class TaskStep:
    """One deterministic planning step in the autonomous task graph."""

    step_id: str
    order: int
    title: str
    action: str
    target: str
    capabilities: list[CapabilityName] = field(default_factory=list)
    estimated_cost: float = 0.0
    complexity: TaskComplexity = "low"


@dataclass(slots=True)
class TaskPlan:
    """Top-level deterministic task plan with DAG metadata."""

    goal: TaskGoal
    steps: list[TaskStep] = field(default_factory=list)
    dependencies: list[TaskDependency] = field(default_factory=list)
    inferred_capabilities: list[CapabilityName] = field(default_factory=list)
    estimated_total_cost: float = 0.0
    overall_complexity: TaskComplexity = "low"

    def as_metadata(self) -> dict[str, object]:
        """Serialize plan deterministically for execution metadata."""
        return {
            "goal": {
                "original_request": self.goal.original_request,
                "actions": list(self.goal.actions),
                "targets": list(self.goal.targets),
                "constraints": list(self.goal.constraints),
                "expected_outputs": list(self.goal.expected_outputs),
            },
            "steps": [
                {
                    "step_id": step.step_id,
                    "order": step.order,
                    "title": step.title,
                    "action": step.action,
                    "target": step.target,
                    "capabilities": list(step.capabilities),
                    "estimated_cost": step.estimated_cost,
                    "complexity": step.complexity,
                }
                for step in self.steps
            ],
            "dependencies": [
                {
                    "predecessor_step_id": edge.predecessor_step_id,
                    "successor_step_id": edge.successor_step_id,
                    "reason": edge.reason,
                }
                for edge in self.dependencies
            ],
            "inferred_capabilities": list(self.inferred_capabilities),
            "estimated_total_cost": self.estimated_total_cost,
            "overall_complexity": self.overall_complexity,
        }
