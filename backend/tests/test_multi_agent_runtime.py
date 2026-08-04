from __future__ import annotations

from typing import Any

from backend.agent_orchestration.runtime import MultiAgentRuntime


def test_multi_agent_runtime_produces_registry_messages_and_artifacts() -> None:
    runtime = MultiAgentRuntime()

    def execute_agent(
        agent_id: str,
        task_prompt: str,
        task_context: dict[str, Any],
    ) -> dict[str, Any]:
        _ = task_context
        return {
            "result": f"{agent_id}:{task_prompt}",
            "reasoning": "completed",
            "tool_outputs": [{"tool": "search"}],
            "memory_references": [{"memory_id": "m-1"}],
            "knowledge_references": [{"source_id": "k-1"}],
            "confidence": 0.88,
            "artifact_type": "markdown",
        }

    result = runtime.run_goal(
        workflow_id="wf-1",
        execution_id="run-1",
        conversation_id="conv-1",
        node_id="agent-node",
        node_name="Research",
        goal="Research objective",
        runtime_context={
            "planned_tasks": [
                {
                    "task_id": "task-1",
                    "title": "Research",
                    "description": "Collect evidence",
                    "required_capabilities": ["general"],
                }
            ],
            "max_retries": 1,
            "retry_policy": "immediate",
        },
        available_agents=[
            {
                "id": "worker-1",
                "capabilities": ["general"],
                "tags": ["research"],
            }
        ],
        execute_agent=execute_agent,
    )

    assert result["status"] == "completed"
    assert len(result["tasks"]) == 1
    assert len(result["messages"]) >= 2
    assert len(result["timeline"]) >= 2
    assert len(result["artifacts"]) == 1
    assert result["metrics"]["tool_count"] == 1
    assert result["metrics"]["memory_lookups"] == 1
    assert result["metrics"]["knowledge_lookups"] == 1


def test_multi_agent_runtime_retries_failed_tasks() -> None:
    runtime = MultiAgentRuntime()
    attempts = {"count": 0}

    def execute_agent(
        agent_id: str,
        task_prompt: str,
        task_context: dict[str, Any],
    ) -> dict[str, Any]:
        _ = (agent_id, task_prompt, task_context)
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("temporary failure")
        return {
            "result": "Recovered",
            "reasoning": "retry succeeded",
            "tool_outputs": [],
            "memory_references": [],
            "knowledge_references": [],
            "confidence": 0.71,
        }

    result = runtime.run_goal(
        workflow_id="wf-2",
        execution_id="run-2",
        conversation_id="conv-2",
        node_id="agent-node",
        node_name="Compute",
        goal="Do computation",
        runtime_context={
            "planned_tasks": [
                {
                    "task_id": "task-a",
                    "title": "Compute",
                    "description": "perform analysis",
                    "required_capabilities": ["general"],
                }
            ],
            "max_retries": 2,
            "retry_policy": "different_agent",
        },
        available_agents=[
            {"id": "worker-1", "capabilities": ["general"]},
            {"id": "worker-2", "capabilities": ["general"]},
        ],
        execute_agent=execute_agent,
    )

    assert attempts["count"] == 2
    assert result["status"] == "completed"
    assert result["metrics"]["retries"] == 1
    assert len(result["retries"]) == 1
