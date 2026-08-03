"""Application service for Agent Studio agent lifecycle operations."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.agent_studio.domain.entities.agent import Agent
from backend.agent_studio.domain.entities.agent_test_run import AgentTestRun
from backend.agent_studio.domain.entities.agent_version import AgentVersion
from backend.agent_studio.models.agent import (
    AgentCreateRequest,
    AgentDashboardResponse,
    AgentTestRequest,
    AgentToolCallResponse,
    AgentUpdateRequest,
    AgentVersionCompareItem,
    AgentVersionCompareResponse,
)
from backend.agent_studio.repository.agent_repository import AgentRepository
from backend.core.logging.logger import LoggerFactory
from backend.llm.client import OllamaClient
from backend.memory.core.memory_manager import MemoryManager
from backend.rag.application.document_service import DocumentRetrievalService
from backend.tools.filesystem_tool import FilesystemTool
from backend.tools.python_tool import PythonTool
from backend.tools.rest_tool import RESTTool

logger = LoggerFactory.get_logger("AgentStudioService")


class AgentService:
    """Orchestrates Agent Studio designer, version, and test-run operations."""

    def __init__(
        self,
        *,
        repository: AgentRepository,
        llm_client: OllamaClient | None = None,
        memory_manager: MemoryManager | None = None,
        document_retrieval_service: DocumentRetrievalService | None = None,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._memory_manager = memory_manager
        self._document_retrieval_service = document_retrieval_service
        self._filesystem_tool = FilesystemTool()
        self._python_tool = PythonTool()
        self._rest_tool = RESTTool()

    def create_agent(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AgentCreateRequest,
    ) -> Agent:
        """Create and persist a new agent."""
        agent = Agent.create(
            agent_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            instructions=payload.instructions,
            system_prompt=payload.system_prompt,
            role=payload.role,
            goal=payload.goal,
            expected_output=payload.expected_output,
            temperature=payload.temperature,
            model=payload.model,
            enabled=payload.enabled,
            color=payload.color,
            icon=payload.icon,
            capabilities=list(payload.capabilities),
            agent_memory_enabled=payload.agent_memory_enabled,
            project_memory_enabled=payload.project_memory_enabled,
            long_term_memory_enabled=payload.long_term_memory_enabled,
            conversation_memory_enabled=payload.conversation_memory_enabled,
            memory_importance=payload.memory_importance,
            memory_scope=payload.memory_scope,
            knowledge_source_ids=list(payload.knowledge_source_ids),
            document_library_ids=list(payload.document_library_ids),
            github_repositories=list(payload.github_repositories),
            sharepoint_sites=list(payload.sharepoint_sites),
            uploaded_document_ids=list(payload.uploaded_document_ids),
            project_knowledge_enabled=payload.project_knowledge_enabled,
            tools_allowed=list(payload.tools_allowed),
            tool_permissions=dict(payload.tool_permissions),
            connectors_allowed=list(payload.connectors_allowed),
            execution_mode=payload.execution_mode,
            approval_required=payload.approval_required,
            max_iterations=payload.max_iterations,
            timeout=payload.timeout,
            retry_count=payload.retry_count,
            retry_policy=dict(payload.retry_policy),
            tags=list(payload.tags),
            connected_agent_ids=list(payload.connected_agent_ids),
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        stored = self._repository.create(agent)
        logger.debug(
            "AGENT_CREATED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            stored.id,
            stored.owner_id,
            stored.workspace_id,
            stored.project_id,
        )
        return stored

    def list_agents(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Agent]:
        """List agents in scope."""
        return self._repository.list_by_scope(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def get_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent | None:
        """Fetch one agent in scope."""
        return self._repository.get_by_id(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    def update_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AgentUpdateRequest,
        change_summary: str = "Updated agent",
    ) -> Agent:
        """Apply a partial update to an agent and capture a new version."""
        current = self._require_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        updated = deepcopy(current)
        data = payload.model_dump(exclude_unset=True)
        for field_name, value in data.items():
            if value is not None and hasattr(updated, field_name):
                setattr(updated, field_name, value)
        updated.touch()
        stored = self._repository.update(updated)
        logger.debug(
            "AGENT_UPDATED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            stored.id,
            stored.owner_id,
            stored.workspace_id,
            stored.project_id,
        )
        return stored

    def delete_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        """Delete an agent in scope."""
        deleted = self._repository.delete(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if deleted:
            logger.debug(
                "AGENT_DELETED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
                agent_id,
                owner_id,
                workspace_id,
                project_id,
            )
        return deleted

    def enable_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        """Enable an agent."""
        agent = self._repository.enable(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        logger.debug(
            "AGENT_ENABLED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            agent.id,
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
        )
        return agent

    def disable_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        """Disable an agent."""
        agent = self._repository.disable(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        logger.debug(
            "AGENT_DISABLED agent_id=%s owner_id=%s workspace_id=%s project_id=%s",
            agent.id,
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
        )
        return agent

    def list_versions(self, agent_id: str) -> list[AgentVersion]:
        """List version history for one agent."""
        return self._repository.list_versions(agent_id)

    def get_version(self, version_id: str) -> AgentVersion | None:
        """Fetch one version snapshot."""
        return self._repository.get_version(version_id)

    def compare_versions(
        self,
        agent_id: str,
        *,
        left_version: int,
        right_version: int,
    ) -> AgentVersionCompareResponse:
        """Compare two snapshots for one agent."""
        versions = {
            version.version_number: version for version in self.list_versions(agent_id)
        }
        left = versions.get(left_version)
        right = versions.get(right_version)
        if left is None or right is None:
            raise KeyError("Version not found")
        differences: list[AgentVersionCompareItem] = []
        keys = sorted(set(left.snapshot.keys()) | set(right.snapshot.keys()))
        for key in keys:
            before = left.snapshot.get(key)
            after = right.snapshot.get(key)
            if before != after:
                differences.append(
                    AgentVersionCompareItem(field=key, before=before, after=after)
                )
        return AgentVersionCompareResponse(
            agent_id=agent_id,
            left_version=left_version,
            right_version=right_version,
            differences=differences,
        )

    def restore_version(
        self,
        agent_id: str,
        *,
        version_id: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        """Restore a previous snapshot as a new saved version."""
        version = self.get_version(version_id)
        if version is None or version.agent_id != agent_id:
            raise KeyError(f"Version not found: {version_id}")
        restored = Agent.from_snapshot(version.snapshot)
        restored.owner_id = owner_id
        restored.workspace_id = workspace_id
        restored.project_id = project_id
        restored.touch()
        return self._repository.update(restored)

    def list_test_runs(self, agent_id: str) -> list[AgentTestRun]:
        """List recorded test runs for one agent."""
        return self._repository.list_test_runs(agent_id)

    def get_dashboard(self, agent_id: str) -> AgentDashboardResponse:
        """Return dashboard metrics for one agent."""
        metrics = self._repository.dashboard_metrics(agent_id)
        return AgentDashboardResponse(
            agent_id=agent_id,
            status=str(metrics.get("status", "unknown")),
            last_run_at=metrics.get("last_run_at"),
            success_rate=float(metrics.get("success_rate", 0.0)),
            average_runtime_ms=float(metrics.get("average_runtime_ms", 0.0)),
            memory_usage=str(metrics.get("memory_usage", "0 modes")),
            knowledge_source_count=int(metrics.get("knowledge_source_count", 0)),
            connected_agent_count=int(metrics.get("connected_agent_count", 0)),
            total_versions=int(metrics.get("total_versions", 0)),
        )

    def run_test_prompt(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        payload: AgentTestRequest,
    ) -> AgentTestRun:
        """Run a real test prompt through the configured LLM and tools."""
        agent = self._require_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if self._llm_client is None:
            raise RuntimeError("LLM client is not configured.")

        started = time.perf_counter()
        available_tools = self._available_tools(agent)
        planning_prompt = self._build_planning_prompt(
            agent, payload.prompt, available_tools
        )
        plan = self._llm_client.generate(
            prompt=planning_prompt,
            system=self._build_system_prompt(agent),
            model=agent.model or None,
            temperature=agent.temperature,
            format_json=True,
        )
        if not isinstance(plan, dict):
            raise RuntimeError("LLM planning response was not valid JSON.")

        reasoning = str(
            plan.get("reasoning")
            or plan.get("reasoning_summary")
            or plan.get("analysis")
            or ""
        ).strip()
        tool_calls = self._normalize_tool_calls(plan.get("tool_calls", []))
        execution: list[dict[str, Any]] = []
        tool_call_responses: list[AgentToolCallResponse] = []
        tool_observations: list[dict[str, Any]] = []

        for tool_call in tool_calls[: max(1, agent.max_iterations)]:
            result = self._execute_tool_call(
                agent=agent,
                tool_call=tool_call,
                allowed_tools=available_tools,
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            execution.append(result)
            tool_call_responses.append(
                AgentToolCallResponse(
                    tool_name=str(tool_call.get("tool_name", "")),
                    input=dict(tool_call.get("input", {})),
                    success=bool(result.get("success", False)),
                    output=dict(result.get("output", {})),
                    duration_ms=float(result.get("duration_ms", 0.0)),
                    error=result.get("error"),
                )
            )
            tool_observations.append(
                {
                    "tool_name": tool_call.get("tool_name", ""),
                    "output": result.get("output", {}),
                    "error": result.get("error"),
                }
            )

        final_prompt = self._build_final_prompt(
            agent=agent,
            user_prompt=payload.prompt,
            reasoning=reasoning,
            tool_observations=tool_observations,
        )
        final_response = self._llm_client.generate(
            prompt=final_prompt,
            system=self._build_system_prompt(agent),
            model=agent.model or None,
            temperature=agent.temperature,
            format_json=True,
        )
        if not isinstance(final_response, dict):
            raise RuntimeError("LLM final response was not valid JSON.")
        final_answer = str(
            final_response.get("final_answer")
            or final_response.get("answer")
            or final_response.get("response")
            or ""
        ).strip()
        if not final_answer:
            raise RuntimeError("LLM final response did not include an answer.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        test_run = AgentTestRun(
            agent_id=agent.id,
            prompt=payload.prompt,
            reasoning=reasoning,
            tool_calls=[dict(item) for item in tool_calls],
            execution=execution,
            final_answer=final_answer,
            success=True,
            timing_ms=elapsed_ms,
        )
        return self._repository.create_test_run(test_run)

    def compare_version_ids(
        self,
        agent_id: str,
        left_version: int,
        right_version: int,
    ) -> AgentVersionCompareResponse:
        """Compatibility wrapper for route layer."""
        return self.compare_versions(
            agent_id,
            left_version=left_version,
            right_version=right_version,
        )

    def _available_tools(self, agent: Agent) -> list[str]:
        if agent.tool_permissions:
            return [name for name, enabled in agent.tool_permissions.items() if enabled]
        return list(agent.tools_allowed)

    @staticmethod
    def _is_tool_allowed(tool_name: str, allowed_tools: list[str]) -> bool:
        normalized = tool_name.lower().strip()
        return any(normalized == item.lower().strip() for item in allowed_tools)

    def _build_system_prompt(self, agent: Agent) -> str:
        return "\n".join(
            [
                agent.system_prompt.strip(),
                f"Role: {agent.role}",
                f"Goal: {agent.goal}",
                f"Expected output: {agent.expected_output}",
                f"Execution mode: {agent.execution_mode}",
            ]
        ).strip()

    def _build_planning_prompt(
        self,
        agent: Agent,
        user_prompt: str,
        available_tools: list[str],
    ) -> str:
        return (
            "Plan the best response using the available tools and return JSON with "
            "keys reasoning, tool_calls, and final_answer_hint. tool_calls must be an "
            "array of objects with tool_name and input. Do not include markdown fences.\n"
            f"Available tools: {', '.join(available_tools) if available_tools else 'none'}\n"
            f"Agent name: {agent.name}\n"
            f"User prompt: {user_prompt}"
        )

    def _build_final_prompt(
        self,
        *,
        agent: Agent,
        user_prompt: str,
        reasoning: str,
        tool_observations: list[dict[str, Any]],
    ) -> str:
        return (
            "Use the tool observations to produce a final JSON object with key "
            "final_answer. Keep it concise and actionable. Do not include markdown fences.\n"
            f"Agent name: {agent.name}\n"
            f"Reasoning summary: {reasoning}\n"
            f"Tool observations: {json.dumps(tool_observations, indent=2, default=str)}\n"
            f"User prompt: {user_prompt}"
        )

    def _normalize_tool_calls(self, raw_calls: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_calls, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "")).strip()
            if not tool_name:
                continue
            normalized.append(
                {
                    "tool_name": tool_name,
                    "input": dict(item.get("input", {})),
                    "purpose": str(item.get("purpose", "")).strip(),
                }
            )
        return normalized

    def _execute_tool_call(
        self,
        *,
        agent: Agent,
        tool_call: dict[str, Any],
        allowed_tools: list[str],
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        tool_name = str(tool_call.get("tool_name", "")).strip().lower()
        tool_input = dict(tool_call.get("input", {}))
        started = time.perf_counter()
        try:
            if allowed_tools and not self._is_tool_allowed(tool_name, allowed_tools):
                raise ValueError(f"Tool not enabled for agent: {tool_name}")
            if tool_name in {"knowledge search", "knowledge", "knowledge_search"}:
                query = str(tool_input.get("query", "")).strip()
                observations = self._knowledge_search(
                    query=query,
                    agent=agent,
                    owner_id=owner_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                )
                return self._tool_result(started, observations)
            if tool_name in {"memory", "memory search", "memory_search"}:
                query = str(tool_input.get("query", "")).strip()
                observations = self._memory_search(
                    query=query,
                    owner_id=owner_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                )
                return self._tool_result(started, observations)
            if tool_name in {"uploads", "uploaded documents", "documents"}:
                query = str(tool_input.get("query", "")).strip()
                observations = self._uploads_search(
                    query=query,
                    owner_id=owner_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                )
                return self._tool_result(started, observations)
            if tool_name in {"filesystem", "filesystemtool"}:
                tool_input.setdefault("workspace_roots", [str(Path.cwd())])
                output = self._filesystem_tool.execute(tool_input)
                return self._tool_result(started, output)
            if tool_name in {"python", "pythontool"}:
                tool_input.setdefault("workspace_root", str(Path.cwd()))
                output = self._python_tool.execute(tool_input)
                return self._tool_result(started, output)
            if tool_name in {"rest", "rest api", "resttool"}:
                output = self._rest_tool.execute(tool_input)
                return self._tool_result(started, output)
            if tool_name in {"github", "sharepoint"}:
                output = self._connector_summary(tool_name, agent, project_id)
                return self._tool_result(started, output)
            raise ValueError(f"Unsupported tool: {tool_call.get('tool_name')}")
        except Exception as exc:  # noqa: BLE001
            return self._tool_error(started, str(exc))

    def _knowledge_search(
        self,
        *,
        query: str,
        agent: Agent,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        if not query:
            return {"items": [], "query": "", "source": "knowledge"}
        if self._document_retrieval_service is None:
            return {"items": [], "query": query, "source": "knowledge"}
        chunks = self._document_retrieval_service.retrieve(
            query,
            top_k=5,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        return {
            "query": query,
            "source": "knowledge",
            "items": [
                {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "text": chunk.text,
                    "score": chunk.score,
                    "metadata": deepcopy(chunk.metadata),
                }
                for chunk in chunks
            ],
            "agent_capabilities": list(agent.capabilities),
        }

    def _memory_search(
        self,
        *,
        query: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        if not query:
            return {"items": [], "query": "", "source": "memory"}
        if self._memory_manager is None:
            return {"items": [], "query": query, "source": "memory"}
        items = self._memory_manager.retrieve_context_memories(
            owner_id,
            query,
            workspace_id=workspace_id,
            project_id=project_id,
            top_n_relevant=5,
            top_n_priority=5,
        )
        return {
            "query": query,
            "source": "memory",
            "items": [
                {
                    "id": item.id,
                    "key": item.key,
                    "value": item.value,
                    "category": item.category,
                    "importance": item.importance,
                    "confidence": item.confidence,
                }
                for item in items
            ],
        }

    def _uploads_search(
        self,
        *,
        query: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        if not query or self._document_retrieval_service is None:
            return {"items": [], "query": query, "source": "uploads"}
        chunks = self._document_retrieval_service.retrieve(
            query,
            top_k=5,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        return {
            "query": query,
            "source": "uploads",
            "items": [
                {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "text": chunk.text,
                    "score": chunk.score,
                    "metadata": deepcopy(chunk.metadata),
                }
                for chunk in chunks
            ],
        }

    def _connector_summary(
        self,
        connector_name: str,
        agent: Agent,
        project_id: str,
    ) -> dict[str, Any]:
        if connector_name == "github":
            items = list(agent.github_repositories)
        else:
            items = list(agent.sharepoint_sites)
        return {
            "source": connector_name,
            "project_id": project_id,
            "items": items,
        }

    def _tool_result(self, started: float, output: Any) -> dict[str, Any]:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "success": True,
            "output": self._json_safe(output),
            "duration_ms": elapsed_ms,
        }

    def _tool_error(self, started: float, error: str) -> dict[str, Any]:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "success": False,
            "output": {},
            "error": error,
            "duration_ms": elapsed_ms,
        }

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            return [self._json_safe(item) for item in value]
        if hasattr(value, "__dict__"):
            return self._json_safe(value.__dict__)
        return str(value)

    def _require_agent(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent:
        agent = self.get_agent(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")
        return agent
