from __future__ import annotations

from backend.execution_graph import (
    ExecutionEdge,
    ExecutionGraph,
    ExecutionGraphBuilder,
    ExecutionGraphSerializer,
    ExecutionNode,
    NodeStatus,
    RetryPolicy,
)
from backend.task_planner.models import TaskDependency, TaskGoal, TaskPlan, TaskStep


def _task_plan() -> TaskPlan:
    return TaskPlan(
        goal=TaskGoal(original_request="Analyze docs and summarize"),
        steps=[
            TaskStep(
                step_id="step-01",
                order=1,
                title="Read files",
                action="read",
                target="docs",
                capabilities=["filesystem"],
                estimated_cost=0.2,
                complexity="low",
            ),
            TaskStep(
                step_id="step-02",
                order=2,
                title="Run python",
                action="execute",
                target="analysis",
                capabilities=["python"],
                estimated_cost=0.8,
                complexity="medium",
            ),
            TaskStep(
                step_id="step-03",
                order=3,
                title="Call rest",
                action="request",
                target="endpoint",
                capabilities=["rest"],
                estimated_cost=0.5,
                complexity="medium",
            ),
        ],
        dependencies=[
            TaskDependency(
                predecessor_step_id="step-01",
                successor_step_id="step-02",
                reason="ordered_execution",
            ),
            TaskDependency(
                predecessor_step_id="step-02",
                successor_step_id="step-03",
                reason="ordered_execution",
            ),
        ],
        inferred_capabilities=["filesystem", "python", "rest"],
        estimated_total_cost=1.5,
        overall_complexity="medium",
    )


def test_graph_builder_from_task_plan_is_deterministic() -> None:
    plan = _task_plan()

    first = ExecutionGraphBuilder.from_task_plan(plan)
    second = ExecutionGraphBuilder.from_task_plan(plan)

    assert first.as_metadata() == second.as_metadata()
    assert first.validate() == []


def test_graph_builder_constructs_nodes_edges_and_metadata() -> None:
    graph = ExecutionGraphBuilder.from_task_plan(_task_plan())

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert graph.metadata["source"] == "task_plan"
    assert graph.metadata["estimated_total_cost"] == 1.5
    assert graph.metadata["overall_complexity"] == "medium"
    assert graph.metadata["inferred_capabilities"] == ["filesystem", "python", "rest"]


def test_node_lookup_and_dependency_lookup() -> None:
    graph = ExecutionGraphBuilder.from_task_plan(_task_plan())

    node = graph.get_node("node:step-02")
    assert node is not None
    assert node.step_id == "step-02"
    assert graph.get_node_by_step_id("step-03") is not None

    dependencies = graph.dependencies_of("node:step-03")
    dependents = graph.dependents_of("node:step-01")
    assert [item.step_id for item in dependencies] == ["step-02"]
    assert [item.step_id for item in dependents] == ["step-02"]


def test_topological_order_is_stable_and_valid() -> None:
    graph = ExecutionGraphBuilder.from_task_plan(_task_plan())

    ordered = graph.topological_order()

    assert [node.step_id for node in ordered] == ["step-01", "step-02", "step-03"]


def test_cycle_detection_and_validation() -> None:
    graph = ExecutionGraph(
        nodes=[
            ExecutionNode(
                node_id="node:a",
                step_id="a",
                order=1,
                title="A",
                action="read",
                target="a",
            ),
            ExecutionNode(
                node_id="node:b",
                step_id="b",
                order=2,
                title="B",
                action="read",
                target="b",
            ),
        ],
        edges=[
            ExecutionEdge("node:a", "node:b", reason="depends"),
            ExecutionEdge("node:b", "node:a", reason="depends"),
        ],
    )

    assert graph.has_cycle() is True
    errors = graph.validate()
    assert "ExecutionGraph contains a cycle" in errors


def test_graph_validation_detects_integrity_issues() -> None:
    graph = ExecutionGraph(
        nodes=[
            ExecutionNode(
                node_id="",
                step_id="dup",
                order=0,
                title="A",
                action="read",
                target="a",
                estimated_cost=-1.0,
                retry_policy=RetryPolicy(max_retries=-1, backoff_seconds=-1.0),
            ),
            ExecutionNode(
                node_id="node:x",
                step_id="dup",
                order=1,
                title="B",
                action="read",
                target="b",
            ),
        ],
        edges=[ExecutionEdge("node:missing", "node:x")],
    )

    errors = graph.validate()

    assert "ExecutionGraph contains duplicate step_id values" in errors
    assert "ExecutionNode.node_id cannot be empty" in errors
    assert "ExecutionNode.order must be > 0 for node " in errors
    assert "ExecutionNode.estimated_cost must be >= 0 for node " in errors
    assert "max_retries must be >= 0" in errors
    assert "backoff_seconds must be >= 0" in errors
    assert "Edge references unknown predecessor node: node:missing" in errors


def test_serializer_returns_metadata_shape() -> None:
    graph = ExecutionGraphBuilder.from_task_plan(_task_plan())

    payload = ExecutionGraphSerializer.to_metadata(graph)

    assert payload["node_count"] == 3
    assert payload["edge_count"] == 2
    assert isinstance(payload["nodes"], list)
    assert isinstance(payload["edges"], list)
    assert payload["nodes"][0]["status"] == NodeStatus.PENDING.value


def test_topological_order_raises_on_cycle() -> None:
    graph = ExecutionGraph(
        nodes=[
            ExecutionNode(
                node_id="node:a",
                step_id="a",
                order=1,
                title="A",
                action="read",
                target="a",
            ),
            ExecutionNode(
                node_id="node:b",
                step_id="b",
                order=2,
                title="B",
                action="read",
                target="b",
            ),
        ],
        edges=[
            ExecutionEdge("node:a", "node:b"),
            ExecutionEdge("node:b", "node:a"),
        ],
    )

    try:
        _ = graph.topological_order()
    except ValueError as exc:
        assert "contains a cycle" in str(exc)
    else:
        raise AssertionError("Expected ValueError for cyclic graph")


def test_regression_builder_ignores_orphan_dependencies() -> None:
    plan = _task_plan()
    plan.dependencies.append(
        TaskDependency(
            predecessor_step_id="missing",
            successor_step_id="step-03",
            reason="invalid",
        )
    )

    graph = ExecutionGraphBuilder.from_task_plan(plan)

    assert len(graph.edges) == 2
    assert graph.validate() == []
