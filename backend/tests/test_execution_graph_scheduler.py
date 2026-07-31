from __future__ import annotations

from backend.execution_graph import (
    ExecutionEdge,
    ExecutionGraph,
    ExecutionGraphCheckpointManager,
    ExecutionGraphExecutor,
    ExecutionGraphScheduler,
    ExecutionNode,
    NodeStatus,
    RetryPolicy,
    graph_runtime_metadata,
)


def _graph() -> ExecutionGraph:
    return ExecutionGraph(
        nodes=[
            ExecutionNode(
                node_id="node:1",
                step_id="step-1",
                order=1,
                title="One",
                action="a",
                target="x",
            ),
            ExecutionNode(
                node_id="node:2",
                step_id="step-2",
                order=2,
                title="Two",
                action="b",
                target="y",
            ),
            ExecutionNode(
                node_id="node:3",
                step_id="step-3",
                order=3,
                title="Three",
                action="c",
                target="z",
            ),
        ],
        edges=[
            ExecutionEdge("node:1", "node:2", reason="depends"),
            ExecutionEdge("node:2", "node:3", reason="depends"),
        ],
    )


def test_scheduler_resolves_dependencies_with_ready_queue() -> None:
    scheduler = ExecutionGraphScheduler(_graph())

    first = scheduler.next_ready_batch()
    assert [node.node_id for node in first] == ["node:1"]
    scheduler.mark_completed("node:1")

    second = scheduler.next_ready_batch()
    assert [node.node_id for node in second] == ["node:2"]
    scheduler.mark_completed("node:2")

    third = scheduler.next_ready_batch()
    assert [node.node_id for node in third] == ["node:3"]
    scheduler.mark_completed("node:3")

    assert scheduler.has_pending() is False


def test_scheduler_retries_then_marks_failed() -> None:
    graph = _graph()
    graph.nodes[0].retry_policy = RetryPolicy(max_retries=1)
    scheduler = ExecutionGraphScheduler(graph)

    ready = scheduler.next_ready_batch()
    assert ready and ready[0].node_id == "node:1"

    scheduler.mark_failed("node:1", error="boom")
    node = graph.get_node("node:1")
    assert node is not None
    assert node.status == NodeStatus.PENDING
    assert scheduler.metadata()["state"]["retry_attempts"]["node:1"] == 1

    retry_batch = scheduler.next_ready_batch()
    assert retry_batch and retry_batch[0].node_id == "node:1"

    scheduler.mark_failed("node:1", error="boom again")
    node = graph.get_node("node:1")
    assert node is not None
    assert node.status == NodeStatus.FAILED
    assert scheduler.metadata()["state"]["failed_nodes"] == ["node:1"]


def test_scheduler_checkpoint_hooks_receive_events() -> None:
    calls: list[str] = []

    def _hook(node: ExecutionNode | None, payload: dict[str, object]) -> None:
        node_id = "none" if node is None else node.node_id
        calls.append(f"{node_id}:{len(payload.get('state', {}))}")

    hooks = {
        "on_scheduler_start": _hook,
        "on_node_start": _hook,
        "on_node_ready": _hook,
        "on_node_completed": _hook,
        "on_scheduler_finish": _hook,
    }

    scheduler = ExecutionGraphScheduler(_graph(), checkpoint_hooks=hooks)
    ready = scheduler.next_ready_batch()
    scheduler.mark_completed(ready[0].node_id)
    ready = scheduler.next_ready_batch()
    scheduler.mark_completed(ready[0].node_id)
    ready = scheduler.next_ready_batch()
    scheduler.mark_completed(ready[0].node_id)

    assert calls
    assert calls[0].startswith("none:")
    assert any(item.startswith("node:1:") for item in calls)
    assert any(item.startswith("node:2:") for item in calls)
    assert any(item.startswith("node:3:") for item in calls)


def test_scheduler_supports_future_parallel_batches() -> None:
    graph = ExecutionGraph(
        nodes=[
            ExecutionNode(
                node_id="node:a",
                step_id="a",
                order=1,
                title="A",
                action="a",
                target="a",
            ),
            ExecutionNode(
                node_id="node:b",
                step_id="b",
                order=2,
                title="B",
                action="b",
                target="b",
            ),
        ],
        edges=[],
    )
    scheduler = ExecutionGraphScheduler(graph, max_parallel=2)

    ready = scheduler.next_ready_batch()

    assert sorted(node.node_id for node in ready) == ["node:a", "node:b"]


def test_executor_runs_dependency_aware_and_sequential_by_default() -> None:
    executor = ExecutionGraphExecutor(_graph())
    executed: list[str] = []

    def _run(node: ExecutionNode) -> dict[str, object]:
        executed.append(node.node_id)
        return {"ok": True}

    result = executor.execute(execute_node=_run)

    assert result.success is True
    assert executed == ["node:1", "node:2", "node:3"]
    assert result.failed_node_ids == []


def test_executor_records_failure_without_api_changes() -> None:
    graph = _graph()
    graph.nodes[0].retry_policy = RetryPolicy(max_retries=0)
    executor = ExecutionGraphExecutor(graph)

    def _run(node: ExecutionNode) -> dict[str, object]:
        if node.node_id == "node:1":
            raise RuntimeError("failed")
        return {"ok": True}

    result = executor.execute(execute_node=_run)

    assert result.success is False
    assert result.failed_node_ids == ["node:1"]
    assert isinstance(result.scheduler_metadata, dict)


def test_scheduler_checkpoint_state_can_resume() -> None:
    graph = _graph()
    scheduler = ExecutionGraphScheduler(graph)

    ready = scheduler.next_ready_batch()
    scheduler.mark_completed(ready[0].node_id)
    state = scheduler.checkpoint_state()

    resumed_scheduler = ExecutionGraphScheduler(_graph(), resume_state=state)
    resumed_ready = resumed_scheduler.next_ready_batch()

    assert [node.node_id for node in resumed_ready] == ["node:2"]


def test_executor_creates_checkpoint_and_supports_resume_state() -> None:
    graph = _graph()
    manager = ExecutionGraphCheckpointManager()
    executor = ExecutionGraphExecutor(graph, checkpoint_manager=manager)

    result = executor.execute(
        execute_node=lambda node: {"node": node.node_id},
        checkpoint_id="cp-1",
    )

    assert result.success is True
    assert result.checkpoint is not None
    assert result.checkpoint["checkpoint_id"] == "cp-1"

    resume_state = manager.resume_state(result.checkpoint)
    resumed = ExecutionGraphExecutor(_graph(), resume_state=resume_state)
    resumed_result = resumed.execute(execute_node=lambda node: {"ok": True})

    # Fully completed checkpoint should not re-run nodes.
    assert resumed_result.executed_node_ids == []
    assert resumed_result.success is True


def test_runtime_metadata_exposes_retries_durations_and_status() -> None:
    graph = _graph()
    graph.nodes[0].retry_policy = RetryPolicy(max_retries=1)
    scheduler = ExecutionGraphScheduler(graph)
    ready = scheduler.next_ready_batch()
    scheduler.mark_failed(ready[0].node_id, error="boom")
    retry = scheduler.next_ready_batch()
    scheduler.mark_completed(retry[0].node_id)

    runtime = graph_runtime_metadata(graph)

    assert runtime["retries"]["node:1"] == 1
    assert runtime["node_status"]["node:1"] == "completed"
    assert runtime["checkpoint_state"]["node:1"] in {"pending", "checkpointed"}
    assert runtime["queue_duration_ms"]["node:1"] >= 0.0
    assert runtime["execution_duration_ms"]["node:1"] >= 0.0
