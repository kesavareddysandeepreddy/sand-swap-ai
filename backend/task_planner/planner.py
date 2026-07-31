"""Deterministic autonomous task planner."""

from __future__ import annotations

from backend.task_planner.models import (
    CapabilityName,
    TaskComplexity,
    TaskDependency,
    TaskGoal,
    TaskPlan,
    TaskStep,
)
from backend.task_planner.parser import TaskRequestParser


class TaskPlanner:
    """Convert user requests into ordered deterministic task plans."""

    _WORKFLOW_INTENT_PHRASES: tuple[str, ...] = (
        "create a workflow",
        "generate workflow",
        "run deployment",
        "run workflow",
        "execute pipeline",
        "execute workflow",
        "workflow execution",
        "orchestrate workflow",
    )

    _CAPABILITY_RULES: tuple[tuple[str, CapabilityName], ...] = (
        ("filesystem", "filesystem"),
        ("file", "filesystem"),
        ("document", "document"),
        ("memory", "memory"),
        ("rag", "rag"),
        ("vision", "vision"),
        ("image", "vision"),
        ("mcp", "mcp"),
        ("python", "python"),
        ("rest", "rest"),
        ("api", "rest"),
        ("workflow", "workflow"),
    )

    _CAPABILITY_COMPLEXITY_COST: dict[CapabilityName, tuple[TaskComplexity, float]] = {
        "filesystem": ("low", 0.3),
        "document": ("low", 0.4),
        "memory": ("medium", 0.8),
        "rag": ("medium", 0.9),
        "vision": ("medium", 1.0),
        "mcp": ("high", 1.5),
        "python": ("medium", 1.1),
        "rest": ("medium", 1.0),
        "workflow": ("high", 1.4),
    }

    _COMPLEXITY_ORDER: dict[TaskComplexity, int] = {
        "low": 1,
        "medium": 2,
        "high": 3,
    }

    def __init__(self, parser: TaskRequestParser | None = None) -> None:
        self.parser = parser or TaskRequestParser()

    def plan(self, request: str) -> TaskPlan:
        """Build a deterministic DAG-based plan for a request."""
        goal = self.parser.parse(request)
        inferred_capabilities = self._infer_capabilities(goal)
        steps = self._build_steps(goal, inferred_capabilities)
        dependencies = self._build_dependencies(steps)
        estimated_total_cost = round(sum(step.estimated_cost for step in steps), 3)
        overall_complexity = self._max_complexity(
            [step.complexity for step in steps] or ["low"]
        )

        return TaskPlan(
            goal=goal,
            steps=steps,
            dependencies=dependencies,
            inferred_capabilities=inferred_capabilities,
            estimated_total_cost=estimated_total_cost,
            overall_complexity=overall_complexity,
        )

    def _infer_capabilities(self, goal: TaskGoal) -> list[CapabilityName]:
        corpus = " ".join(
            [goal.original_request, *goal.actions, *goal.targets, *goal.constraints]
        ).lower()
        capabilities: list[CapabilityName] = []
        for token, capability in self._CAPABILITY_RULES:
            if capability == "workflow" and not self._requires_workflow_capability(
                corpus
            ):
                continue
            if token in corpus and capability not in capabilities:
                capabilities.append(capability)

        return sorted(capabilities)

    def _requires_workflow_capability(self, corpus: str) -> bool:
        return any(phrase in corpus for phrase in self._WORKFLOW_INTENT_PHRASES)

    def _build_steps(
        self,
        goal: TaskGoal,
        capabilities: list[CapabilityName],
    ) -> list[TaskStep]:
        steps: list[TaskStep] = []
        for index, capability in enumerate(capabilities, start=1):
            complexity, base_cost = self._CAPABILITY_COMPLEXITY_COST[capability]
            signal_count = max(
                1,
                len(goal.actions) + len(goal.targets) + len(goal.constraints),
            )
            estimated_cost = round(base_cost + (signal_count * 0.01), 3)

            action = self._pick_action(goal.actions, capability)
            target = self._pick_target(goal.targets, capability)

            steps.append(
                TaskStep(
                    step_id=f"step-{index:02d}",
                    order=index,
                    title=f"{capability.upper()} {action}",
                    action=action,
                    target=target,
                    capabilities=[capability],
                    estimated_cost=estimated_cost,
                    complexity=complexity,
                )
            )
        return steps

    @staticmethod
    def _build_dependencies(steps: list[TaskStep]) -> list[TaskDependency]:
        dependencies: list[TaskDependency] = []
        for previous, current in zip(steps, steps[1:], strict=False):
            dependencies.append(
                TaskDependency(
                    predecessor_step_id=previous.step_id,
                    successor_step_id=current.step_id,
                    reason="ordered_execution",
                )
            )
        return dependencies

    @staticmethod
    def _pick_action(actions: list[str], capability: CapabilityName) -> str:
        if actions:
            return actions[0]
        defaults: dict[CapabilityName, str] = {
            "filesystem": "read",
            "document": "inspect",
            "memory": "retrieve",
            "rag": "retrieve",
            "vision": "analyze",
            "mcp": "invoke",
            "python": "execute",
            "rest": "request",
            "workflow": "coordinate",
        }
        return defaults[capability]

    @staticmethod
    def _pick_target(targets: list[str], capability: CapabilityName) -> str:
        if targets:
            return targets[0]
        return capability

    def _max_complexity(self, values: list[TaskComplexity]) -> TaskComplexity:
        return max(values, key=lambda value: self._COMPLEXITY_ORDER[value])
