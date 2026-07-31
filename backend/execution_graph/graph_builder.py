"""Deterministic builder from TaskPlan to ExecutionGraph."""

from __future__ import annotations

from backend.execution_graph.models import (
    ExecutionEdge,
    ExecutionGraph,
    ExecutionNode,
    RetryPolicy,
)
from backend.task_planner.models import TaskPlan


class ExecutionGraphBuilder:
    """Build execution graphs from deterministic task plans."""

    @staticmethod
    def from_task_plan(task_plan: TaskPlan) -> ExecutionGraph:
        """Build an ExecutionGraph from TaskPlan without behavior changes."""
        nodes = [
            ExecutionNode(
                node_id=f"node:{step.step_id}",
                step_id=step.step_id,
                order=step.order,
                title=step.title,
                action=step.action,
                target=step.target,
                capabilities=list(step.capabilities),
                estimated_cost=step.estimated_cost,
                complexity=step.complexity,
                retry_policy=RetryPolicy(),
                metadata={"source": "task_plan"},
            )
            for step in sorted(
                task_plan.steps, key=lambda item: (item.order, item.step_id)
            )
        ]

        step_to_node = {node.step_id: node.node_id for node in nodes}
        edges = [
            ExecutionEdge(
                predecessor_node_id=step_to_node[dependency.predecessor_step_id],
                successor_node_id=step_to_node[dependency.successor_step_id],
                reason=dependency.reason,
                metadata={"source": "task_plan"},
            )
            for dependency in task_plan.dependencies
            if dependency.predecessor_step_id in step_to_node
            and dependency.successor_step_id in step_to_node
        ]

        return ExecutionGraph(
            nodes=nodes,
            edges=edges,
            metadata={
                "source": "task_plan",
                "estimated_total_cost": task_plan.estimated_total_cost,
                "overall_complexity": task_plan.overall_complexity,
                "inferred_capabilities": list(task_plan.inferred_capabilities),
            },
        )
