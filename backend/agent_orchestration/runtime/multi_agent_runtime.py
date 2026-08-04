"""Enterprise multi-agent runtime for workflow agent-node execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from backend.agent_orchestration.domain.run import AgentLifecycleState, AgentMessageType

AgentExecutionCallback = Callable[[str, str, dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class RuntimeTask:
    """Delegable unit of work produced by planner and coordinated by supervisor."""

    task_id: str
    title: str
    description: str
    required_capabilities: list[str] = field(default_factory=list)
    assigned_agent_id: str = ""
    status: str = "waiting"
    retry_count: int = 0
    error: str = ""
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeAgent:
    """Runtime view of one collaborative agent."""

    agent_id: str
    role: str
    state: str = AgentLifecycleState.CREATED
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    knowledge_sources: list[str] = field(default_factory=list)
    current_task_id: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_runtime_ms: float = 0.0


class MultiAgentRuntime:
    """Coordinates supervisor, planner, and worker collaboration inside a workflow run."""

    def run_goal(
        self,
        *,
        workflow_id: str,
        execution_id: str,
        conversation_id: str,
        node_id: str,
        node_name: str,
        goal: str,
        runtime_context: dict[str, Any],
        available_agents: list[dict[str, Any]],
        execute_agent: AgentExecutionCallback,
    ) -> dict[str, Any]:
        """Execute one collaborative goal and return structured runtime outputs."""
        started = perf_counter()
        retry_policy = str(runtime_context.get("retry_policy", "immediate"))
        max_retries = int(runtime_context.get("max_retries", 1) or 1)
        planner_id = str(runtime_context.get("planner_agent_id", "planner-agent"))
        supervisor_id = str(
            runtime_context.get("supervisor_agent_id", "supervisor-agent")
        )

        registry = self._build_registry(
            available_agents=available_agents,
            planner_id=planner_id,
            supervisor_id=supervisor_id,
        )
        timeline: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        retries: list[dict[str, Any]] = []

        self._set_state(registry, supervisor_id, AgentLifecycleState.RUNNING)
        self._set_state(registry, planner_id, AgentLifecycleState.PLANNING)

        timeline.append(
            self._timeline_event(
                agent_id=supervisor_id,
                action="workflow-supervision-started",
                metadata={"node_id": node_id, "node_name": node_name},
            )
        )

        tasks = self._plan_tasks(goal=goal, runtime_context=runtime_context)
        for task in tasks:
            task.required_capabilities = task.required_capabilities or ["general"]

        self._set_state(registry, planner_id, AgentLifecycleState.COMPLETED)

        messages.append(
            self._message(
                workflow_id=workflow_id,
                execution_id=execution_id,
                conversation_id=conversation_id,
                sender_agent=planner_id,
                receiver_agent=supervisor_id,
                task_id="plan",
                message_type=AgentMessageType.STATUS_UPDATE,
                payload={"planned_tasks": [self._task_dict(item) for item in tasks]},
                reasoning_summary="Planner decomposed goal into executable tasks.",
                confidence=0.75,
                priority="high",
            )
        )

        completed_tasks = 0
        failed_tasks = 0
        tool_count = 0
        memory_lookups = 0
        knowledge_lookups = 0

        for task in tasks:
            assigned_agent = self._match_agent(task, registry)
            if not assigned_agent:
                task.status = "failed"
                task.error = "No capable agent available"
                failed_tasks += 1
                timeline.append(
                    self._timeline_event(
                        agent_id=supervisor_id,
                        action="task-assignment-failed",
                        metadata={
                            "task_id": task.task_id,
                            "required_capabilities": list(task.required_capabilities),
                        },
                    )
                )
                messages.append(
                    self._message(
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        conversation_id=conversation_id,
                        sender_agent=supervisor_id,
                        receiver_agent=planner_id,
                        task_id=task.task_id,
                        message_type=AgentMessageType.ERROR,
                        payload={"error": task.error},
                        reasoning_summary="Supervisor could not find a capable worker.",
                        confidence=0.95,
                        priority="high",
                    )
                )
                continue

            task.assigned_agent_id = assigned_agent
            self._set_state(registry, assigned_agent, AgentLifecycleState.RUNNING)
            self._set_current_task(registry, assigned_agent, task.task_id)

            messages.append(
                self._message(
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    conversation_id=conversation_id,
                    sender_agent=supervisor_id,
                    receiver_agent=assigned_agent,
                    task_id=task.task_id,
                    message_type=AgentMessageType.TASK_REQUEST,
                    payload={
                        "title": task.title,
                        "description": task.description,
                        "required_capabilities": list(task.required_capabilities),
                    },
                    reasoning_summary="Supervisor delegated planned task to worker.",
                    confidence=0.82,
                    priority="normal",
                )
            )

            task_started = perf_counter()
            success = False
            while task.retry_count <= max_retries and not success:
                try:
                    response = execute_agent(
                        assigned_agent,
                        task.description,
                        {
                            "goal": goal,
                            "task_id": task.task_id,
                            "node_id": node_id,
                            "workflow_id": workflow_id,
                            "execution_id": execution_id,
                            "shared_context": dict(runtime_context),
                        },
                    )
                    task.result = dict(response)
                    task.status = "completed"
                    success = True
                    completed_tasks += 1

                    task_artifact = {
                        "artifact_id": str(uuid4()),
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "task_id": task.task_id,
                        "producer_agent": assigned_agent,
                        "artifact_type": str(
                            response.get("artifact_type", "json")
                        ).lower(),
                        "name": f"{task.title}-output",
                        "content": response.get("result", response),
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                    artifacts.append(task_artifact)

                    tool_outputs = response.get("tool_outputs", [])
                    if isinstance(tool_outputs, list):
                        tool_count += len(tool_outputs)
                    memory_refs = response.get("memory_references", [])
                    if isinstance(memory_refs, list):
                        memory_lookups += len(memory_refs)
                    knowledge_refs = response.get("knowledge_references", [])
                    if isinstance(knowledge_refs, list):
                        knowledge_lookups += len(knowledge_refs)

                    messages.append(
                        self._message(
                            workflow_id=workflow_id,
                            execution_id=execution_id,
                            conversation_id=conversation_id,
                            sender_agent=assigned_agent,
                            receiver_agent=supervisor_id,
                            task_id=task.task_id,
                            message_type=AgentMessageType.TASK_RESULT,
                            payload=dict(response),
                            reasoning_summary=str(
                                response.get("reasoning", "Worker completed task.")
                            ),
                            confidence=float(response.get("confidence", 0.72) or 0.72),
                            attachments=[task_artifact],
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    task.retry_count += 1
                    task.error = str(exc)
                    if task.retry_count > max_retries:
                        task.status = "failed"
                        failed_tasks += 1
                        messages.append(
                            self._message(
                                workflow_id=workflow_id,
                                execution_id=execution_id,
                                conversation_id=conversation_id,
                                sender_agent=assigned_agent,
                                receiver_agent=supervisor_id,
                                task_id=task.task_id,
                                message_type=AgentMessageType.ERROR,
                                payload={"error": task.error},
                                reasoning_summary="Worker failed and exhausted retries.",
                                confidence=0.9,
                                priority="high",
                            )
                        )
                        break

                    retries.append(
                        {
                            "task_id": task.task_id,
                            "attempt": task.retry_count,
                            "policy": retry_policy,
                            "from_agent": assigned_agent,
                            "error": task.error,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    timeline.append(
                        self._timeline_event(
                            agent_id=supervisor_id,
                            action="retry-scheduled",
                            metadata={
                                "task_id": task.task_id,
                                "attempt": task.retry_count,
                                "policy": retry_policy,
                                "error": task.error,
                            },
                        )
                    )
                    if retry_policy == "different_agent":
                        alternate_agent = self._match_agent(
                            task,
                            registry,
                            exclude={assigned_agent},
                        )
                        if alternate_agent:
                            assigned_agent = alternate_agent
                            task.assigned_agent_id = alternate_agent
                            self._set_current_task(
                                registry, assigned_agent, task.task_id
                            )

            task_duration = round((perf_counter() - task_started) * 1000, 3)
            self._add_runtime(registry, assigned_agent, task_duration)
            if task.status == "completed":
                self._set_state(registry, assigned_agent, AgentLifecycleState.COMPLETED)
                self._count_success(registry, assigned_agent)
            else:
                self._set_state(registry, assigned_agent, AgentLifecycleState.FAILED)
                self._count_failure(registry, assigned_agent)

            timeline.append(
                self._timeline_event(
                    agent_id=assigned_agent,
                    action="task-finished",
                    duration_ms=task_duration,
                    metadata={
                        "task_id": task.task_id,
                        "status": task.status,
                        "retry_count": task.retry_count,
                    },
                )
            )

        supervisor_state = (
            AgentLifecycleState.COMPLETED
            if failed_tasks == 0
            else AgentLifecycleState.FAILED
        )
        self._set_state(registry, supervisor_id, supervisor_state)

        total_ms = round((perf_counter() - started) * 1000, 3)
        timeline.append(
            self._timeline_event(
                agent_id=supervisor_id,
                action="workflow-supervision-finished",
                duration_ms=total_ms,
                metadata={
                    "completed_tasks": completed_tasks,
                    "failed_tasks": failed_tasks,
                },
            )
        )

        aggregated_result = {
            "result": "\n\n".join(
                str(task.result.get("result", "")).strip()
                for task in tasks
                if task.status == "completed"
            ).strip(),
            "reasoning": "Supervisor aggregated worker outputs.",
            "confidence": 0.83 if failed_tasks == 0 else 0.58,
            "status": "completed" if failed_tasks == 0 else "failed",
            "tasks": [self._task_dict(task) for task in tasks],
            "messages": list(messages),
            "artifacts": list(artifacts),
            "timeline": list(timeline),
            "registry": self._registry_snapshot(registry),
            "supervisor": {
                "agent_id": supervisor_id,
                "state": supervisor_state,
                "total_tasks": len(tasks),
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "retry_policy": retry_policy,
            },
            "metrics": {
                "execution_time_ms": total_ms,
                "per_agent_duration_ms": {
                    key: value.total_runtime_ms for key, value in registry.items()
                },
                "waiting_time_ms": 0.0,
                "retries": len(retries),
                "failures": failed_tasks,
                "tool_count": tool_count,
                "memory_lookups": memory_lookups,
                "knowledge_lookups": knowledge_lookups,
                "artifacts": len(artifacts),
                "tokens": 0,
                "cost": 0.0,
            },
            "retries": retries,
        }
        return aggregated_result

    @staticmethod
    def _plan_tasks(goal: str, runtime_context: dict[str, Any]) -> list[RuntimeTask]:
        configured = runtime_context.get("planned_tasks")
        if isinstance(configured, list) and configured:
            tasks: list[RuntimeTask] = []
            for index, item in enumerate(configured):
                if not isinstance(item, dict):
                    continue
                tasks.append(
                    RuntimeTask(
                        task_id=str(item.get("task_id", f"task-{index + 1}")),
                        title=str(item.get("title", f"Task {index + 1}")),
                        description=str(item.get("description", "")),
                        required_capabilities=[
                            str(capability)
                            for capability in item.get("required_capabilities", [])
                            if isinstance(capability, str)
                        ],
                    )
                )
            if tasks:
                return tasks

        normalized_goal = goal.strip() or "Execute workflow objective"
        return [
            RuntimeTask(
                task_id="task-1",
                title="Primary Task",
                description=normalized_goal,
                required_capabilities=["general"],
            )
        ]

    @staticmethod
    def _build_registry(
        *,
        available_agents: list[dict[str, Any]],
        planner_id: str,
        supervisor_id: str,
    ) -> dict[str, RuntimeAgent]:
        registry: dict[str, RuntimeAgent] = {
            supervisor_id: RuntimeAgent(agent_id=supervisor_id, role="supervisor"),
            planner_id: RuntimeAgent(agent_id=planner_id, role="planner"),
        }
        for item in available_agents:
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get("id", "")).strip()
            if not agent_id:
                continue
            if agent_id in registry:
                continue
            capabilities = [
                str(capability)
                for capability in item.get("capabilities", ["general"])
                if isinstance(capability, str)
            ]
            tags = [str(tag) for tag in item.get("tags", []) if isinstance(tag, str)]
            allowed_tools = [
                str(tool)
                for tool in item.get("allowed_tools", [])
                if isinstance(tool, str)
            ]
            knowledge_sources = [
                str(source)
                for source in item.get("knowledge_sources", [])
                if isinstance(source, str)
            ]
            registry[agent_id] = RuntimeAgent(
                agent_id=agent_id,
                role="worker",
                capabilities=capabilities or ["general"],
                tags=tags,
                allowed_tools=allowed_tools,
                knowledge_sources=knowledge_sources,
            )
        return registry

    @staticmethod
    def _match_agent(
        task: RuntimeTask,
        registry: dict[str, RuntimeAgent],
        *,
        exclude: set[str] | None = None,
    ) -> str:
        blocked = exclude or set()
        workers = [
            agent
            for agent in registry.values()
            if agent.role == "worker" and agent.agent_id not in blocked
        ]
        if not workers:
            return ""
        required = {capability.lower() for capability in task.required_capabilities}
        for worker in workers:
            capabilities = {value.lower() for value in worker.capabilities}
            if not required or required.intersection(capabilities):
                return worker.agent_id
        return workers[0].agent_id

    @staticmethod
    def _set_state(
        registry: dict[str, RuntimeAgent],
        agent_id: str,
        state: str,
    ) -> None:
        if agent_id in registry:
            registry[agent_id].state = state

    @staticmethod
    def _set_current_task(
        registry: dict[str, RuntimeAgent],
        agent_id: str,
        task_id: str,
    ) -> None:
        if agent_id in registry:
            registry[agent_id].current_task_id = task_id

    @staticmethod
    def _add_runtime(
        registry: dict[str, RuntimeAgent],
        agent_id: str,
        duration_ms: float,
    ) -> None:
        if agent_id in registry:
            registry[agent_id].total_runtime_ms += duration_ms

    @staticmethod
    def _count_success(registry: dict[str, RuntimeAgent], agent_id: str) -> None:
        if agent_id in registry:
            registry[agent_id].tasks_completed += 1

    @staticmethod
    def _count_failure(registry: dict[str, RuntimeAgent], agent_id: str) -> None:
        if agent_id in registry:
            registry[agent_id].tasks_failed += 1

    @staticmethod
    def _registry_snapshot(registry: dict[str, RuntimeAgent]) -> dict[str, Any]:
        running = [
            agent.agent_id
            for agent in registry.values()
            if agent.state == AgentLifecycleState.RUNNING
        ]
        waiting = [
            agent.agent_id
            for agent in registry.values()
            if agent.state in {AgentLifecycleState.CREATED, AgentLifecycleState.WAITING}
        ]
        busy = [agent.agent_id for agent in registry.values() if agent.current_task_id]
        idle = [
            agent.agent_id for agent in registry.values() if not agent.current_task_id
        ]
        return {
            "running_agents": running,
            "waiting_agents": waiting,
            "busy_agents": busy,
            "idle_agents": idle,
            "available_agents": sorted(registry.keys()),
            "entries": {
                key: {
                    "agent_id": value.agent_id,
                    "role": value.role,
                    "state": value.state,
                    "capabilities": list(value.capabilities),
                    "tags": list(value.tags),
                    "allowed_tools": list(value.allowed_tools),
                    "knowledge_sources": list(value.knowledge_sources),
                    "current_task_id": value.current_task_id,
                    "tasks_completed": value.tasks_completed,
                    "tasks_failed": value.tasks_failed,
                    "total_runtime_ms": value.total_runtime_ms,
                }
                for key, value in registry.items()
            },
        }

    @staticmethod
    def _timeline_event(
        *,
        agent_id: str,
        action: str,
        duration_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        details = dict(metadata or {})
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": agent_id,
            "action": action,
            "duration_ms": duration_ms,
            "memory_accessed": list(details.get("memory_accessed", [])),
            "knowledge_accessed": list(details.get("knowledge_accessed", [])),
            "tools_used": list(details.get("tools_used", [])),
            "artifacts_produced": list(details.get("artifacts_produced", [])),
            "metadata": details,
        }

    @staticmethod
    def _message(
        *,
        workflow_id: str,
        execution_id: str,
        conversation_id: str,
        sender_agent: str,
        receiver_agent: str,
        task_id: str,
        message_type: str,
        payload: dict[str, Any],
        reasoning_summary: str,
        confidence: float,
        priority: str = "normal",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "message_id": str(uuid4()),
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "conversation_id": conversation_id,
            "sender_agent": sender_agent,
            "receiver_agent": receiver_agent,
            "task_id": task_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "priority": priority,
            "message_type": message_type,
            "payload": dict(payload),
            "reasoning_summary": reasoning_summary,
            "confidence": confidence,
            "attachments": list(attachments or []),
        }

    @staticmethod
    def _task_dict(task: RuntimeTask) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "required_capabilities": list(task.required_capabilities),
            "assigned_agent_id": task.assigned_agent_id,
            "status": task.status,
            "retry_count": task.retry_count,
            "error": task.error,
            "result": dict(task.result),
        }
