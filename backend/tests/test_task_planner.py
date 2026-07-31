from __future__ import annotations

from backend.task_planner.models import TaskPlan
from backend.task_planner.parser import TaskRequestParser
from backend.task_planner.planner import TaskPlanner


def test_parser_extracts_actions_targets_constraints_and_outputs() -> None:
    parser = TaskRequestParser()
    goal = parser.parse(
        "Read filesystem metadata and summarize documents. "
        "Do not modify files. Return a JSON output."
    )

    assert goal.original_request.startswith("Read filesystem metadata")
    assert "read" in goal.actions
    assert "summarize" in goal.actions
    assert "filesystem" in goal.targets
    assert any(item.lower().startswith("do not") for item in goal.constraints)
    assert any("return" in item.lower() for item in goal.expected_outputs)


def test_planner_builds_dag_and_orders_steps() -> None:
    planner = TaskPlanner()
    plan = planner.plan("Read file and call REST API then run workflow")

    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) >= 1
    assert [step.order for step in plan.steps] == list(range(1, len(plan.steps) + 1))

    if len(plan.steps) > 1:
        assert len(plan.dependencies) == len(plan.steps) - 1
        for edge in plan.dependencies:
            assert edge.predecessor_step_id != edge.successor_step_id


def test_planner_infers_expected_capabilities() -> None:
    planner = TaskPlanner()
    plan = planner.plan(
        "Use filesystem and memory, then query RAG and call MCP with python + rest and create a workflow"
    )

    assert "filesystem" in plan.inferred_capabilities
    assert "memory" in plan.inferred_capabilities
    assert "rag" in plan.inferred_capabilities
    assert "mcp" in plan.inferred_capabilities
    assert "python" in plan.inferred_capabilities
    assert "rest" in plan.inferred_capabilities
    assert "workflow" in plan.inferred_capabilities


def test_planner_computes_cost_and_complexity() -> None:
    planner = TaskPlanner()
    plan = planner.plan("Invoke MCP and workflow with REST automation")

    assert plan.estimated_total_cost > 0
    assert plan.overall_complexity in {"low", "medium", "high"}
    assert any(step.estimated_cost > 0 for step in plan.steps)


def test_planner_is_deterministic_for_identical_input() -> None:
    planner = TaskPlanner()
    request = "Read filesystem and query documents with RAG"

    first = planner.plan(request).as_metadata()
    second = planner.plan(request).as_metadata()

    assert first == second


def test_planner_does_not_infer_workflow_for_repository_question() -> None:
    planner = TaskPlanner()

    plan = planner.plan("Explain the architecture of the sand-swap-ai project.")

    assert "workflow" not in plan.inferred_capabilities
    assert plan.inferred_capabilities == []


def test_planner_infers_workflow_only_for_explicit_workflow_request() -> None:
    planner = TaskPlanner()

    plan = planner.plan("Create a workflow and execute pipeline steps.")

    assert "workflow" in plan.inferred_capabilities
