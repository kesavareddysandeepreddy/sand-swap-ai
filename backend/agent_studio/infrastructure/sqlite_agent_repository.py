"""SQLite repository for Agent Studio agents."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agent_studio.domain.entities.agent import Agent
from backend.agent_studio.domain.entities.agent_test_run import AgentTestRun
from backend.agent_studio.domain.entities.agent_version import AgentVersion
from backend.agent_studio.repository.agent_repository import AgentRepository
from backend.database.sqlite_connection import create_sqlite_connection


class SQLiteAgentRepository(AgentRepository):
    """SQLite-backed Agent Studio repository."""

    def __init__(self, db_path: str = "data/agent_studio/agent_studio.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    role TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    short_term_enabled INTEGER NOT NULL,
                    long_term_enabled INTEGER NOT NULL,
                    project_memory_enabled INTEGER NOT NULL,
                    tools_allowed TEXT NOT NULL,
                    connectors_allowed TEXT NOT NULL,
                    approval_required INTEGER NOT NULL,
                    max_iterations INTEGER NOT NULL,
                    timeout INTEGER NOT NULL,
                    retry_policy TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self._ensure_agent_columns(
                [
                    ("snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
                ]
            )
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS agent_versions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    change_summary TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS agent_test_runs (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    tool_calls_json TEXT NOT NULL,
                    execution_json TEXT NOT NULL,
                    final_answer TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    error TEXT,
                    timing_ms REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.commit()

    def _ensure_agent_columns(self, columns: list[tuple[str, str]]) -> None:
        existing = {
            str(row[1])
            for row in self._connection.execute("PRAGMA table_info(agents)").fetchall()
        }
        for column_name, column_definition in columns:
            if column_name in existing:
                continue
            self._connection.execute(
                f"ALTER TABLE agents ADD COLUMN {column_name} {column_definition}"
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _bool(value: bool) -> int:
        return 1 if value else 0

    @staticmethod
    def _parse_json(value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _row_to_agent(row: sqlite3.Row | None) -> Agent | None:
        if row is None:
            return None
        snapshot = SQLiteAgentRepository._parse_json(row["snapshot_json"], {})
        if isinstance(snapshot, dict) and snapshot:
            payload = dict(snapshot)
        else:
            payload = {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "description": str(row["description"]),
                "instructions": "",
                "system_prompt": str(row["system_prompt"]),
                "role": str(row["role"]),
                "goal": str(row["objective"]),
                "expected_output": "",
                "temperature": 0.2,
                "model": "",
                "enabled": bool(int(row["enabled"])),
                "color": "#2563eb",
                "icon": "sparkles",
                "capabilities": [],
                "agent_memory_enabled": bool(int(row["short_term_enabled"])),
                "project_memory_enabled": bool(int(row["project_memory_enabled"])),
                "long_term_memory_enabled": bool(int(row["long_term_enabled"])),
                "conversation_memory_enabled": True,
                "memory_importance": 0.5,
                "memory_scope": "project",
                "knowledge_source_ids": [],
                "document_library_ids": [],
                "github_repositories": [],
                "sharepoint_sites": [],
                "uploaded_document_ids": [],
                "project_knowledge_enabled": True,
                "tools_allowed": SQLiteAgentRepository._parse_json(
                    row["tools_allowed"], []
                ),
                "tool_permissions": {},
                "connectors_allowed": SQLiteAgentRepository._parse_json(
                    row["connectors_allowed"], []
                ),
                "execution_mode": "sequential",
                "approval_required": bool(int(row["approval_required"])),
                "max_iterations": int(row["max_iterations"]),
                "timeout": int(row["timeout"]),
                "retry_count": 0,
                "retry_policy": SQLiteAgentRepository._parse_json(
                    row["retry_policy"], {}
                ),
                "tags": SQLiteAgentRepository._parse_json(row["tags"], []),
                "connected_agent_ids": [],
                "owner_id": str(row["owner_id"]),
                "workspace_id": str(row["workspace_id"]),
                "project_id": str(row["project_id"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["updated_at"] = datetime.fromisoformat(str(payload["updated_at"]))
        payload["tools_allowed"] = list(payload.get("tools_allowed", []))
        payload["tool_permissions"] = dict(payload.get("tool_permissions", {}))
        payload["connectors_allowed"] = list(payload.get("connectors_allowed", []))
        payload["capabilities"] = list(payload.get("capabilities", []))
        payload["knowledge_source_ids"] = list(payload.get("knowledge_source_ids", []))
        payload["document_library_ids"] = list(payload.get("document_library_ids", []))
        payload["github_repositories"] = list(payload.get("github_repositories", []))
        payload["sharepoint_sites"] = list(payload.get("sharepoint_sites", []))
        payload["uploaded_document_ids"] = list(
            payload.get("uploaded_document_ids", [])
        )
        payload["tags"] = list(payload.get("tags", []))
        payload["connected_agent_ids"] = list(payload.get("connected_agent_ids", []))
        return Agent(**payload)

    @staticmethod
    def _serialize(agent: Agent) -> tuple[Any, ...]:
        return (
            agent.id,
            agent.name,
            agent.description,
            agent.role,
            agent.goal,
            agent.system_prompt,
            SQLiteAgentRepository._bool(agent.enabled),
            SQLiteAgentRepository._bool(agent.agent_memory_enabled),
            SQLiteAgentRepository._bool(agent.long_term_memory_enabled),
            SQLiteAgentRepository._bool(agent.project_memory_enabled),
            json.dumps(agent.tools_allowed),
            json.dumps(agent.connectors_allowed),
            SQLiteAgentRepository._bool(agent.approval_required),
            agent.max_iterations,
            agent.timeout,
            json.dumps(agent.retry_policy),
            json.dumps(agent.tags),
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
            agent.created_at.isoformat(),
            agent.updated_at.isoformat(),
            json.dumps(agent.to_snapshot()),
        )

    def create(self, agent: Agent) -> Agent:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agents (
                    id, name, description, role, objective, system_prompt,
                    enabled, short_term_enabled, long_term_enabled,
                    project_memory_enabled, tools_allowed, connectors_allowed,
                    approval_required, max_iterations, timeout, retry_policy,
                    tags, owner_id, workspace_id, project_id, created_at, updated_at,
                    snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._serialize(agent),
            )
            self._connection.commit()
        self.create_version(
            AgentVersion(
                agent_id=agent.id,
                version_number=1,
                change_summary="Created agent",
                snapshot=agent.to_snapshot(),
            )
        )
        return agent

    def update(self, agent: Agent) -> Agent:
        updated = replace(agent, updated_at=datetime.now(UTC))
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE agents
                SET name = ?, description = ?, role = ?, objective = ?, system_prompt = ?,
                    enabled = ?, short_term_enabled = ?, long_term_enabled = ?,
                    project_memory_enabled = ?, tools_allowed = ?, connectors_allowed = ?,
                    approval_required = ?, max_iterations = ?, timeout = ?, retry_policy = ?,
                    tags = ?, owner_id = ?, workspace_id = ?, project_id = ?, updated_at = ?,
                    snapshot_json = ?
                WHERE id = ?
                  AND owner_id = ?
                  AND workspace_id = ?
                  AND project_id = ?
                """,
                (
                    updated.name,
                    updated.description,
                    updated.role,
                    updated.goal,
                    updated.system_prompt,
                    self._bool(updated.enabled),
                    self._bool(updated.agent_memory_enabled),
                    self._bool(updated.long_term_memory_enabled),
                    self._bool(updated.project_memory_enabled),
                    json.dumps(updated.tools_allowed),
                    json.dumps(updated.connectors_allowed),
                    self._bool(updated.approval_required),
                    updated.max_iterations,
                    updated.timeout,
                    json.dumps(updated.retry_policy),
                    json.dumps(updated.tags),
                    updated.owner_id,
                    updated.workspace_id,
                    updated.project_id,
                    updated.updated_at.isoformat(),
                    json.dumps(updated.to_snapshot()),
                    updated.id,
                    updated.owner_id,
                    updated.workspace_id,
                    updated.project_id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Agent not found: {updated.id}")

        next_version = self.get_latest_version_number(updated.id) + 1
        self.create_version(
            AgentVersion(
                agent_id=updated.id,
                version_number=next_version,
                change_summary="Updated agent",
                snapshot=updated.to_snapshot(),
            )
        )
        return updated

    def delete(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM agents
                WHERE id = ? AND owner_id = ? AND workspace_id = ? AND project_id = ?
                """,
                (agent_id, owner_id, workspace_id, project_id),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_by_id(
        self,
        agent_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Agent | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM agents
                WHERE id = ? AND owner_id = ? AND workspace_id = ? AND project_id = ?
                """,
                (agent_id, owner_id, workspace_id, project_id),
            ).fetchone()
        return self._row_to_agent(row)

    def list_by_scope(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Agent]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM agents
                WHERE owner_id = ? AND workspace_id = ? AND project_id = ?
                ORDER BY updated_at DESC
                """,
                (owner_id, workspace_id, project_id),
            ).fetchall()
        return [agent for agent in (self._row_to_agent(row) for row in rows) if agent]

    def enable(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> Agent:
        agent = self.get_by_id(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if agent is None:
            raise ValueError(f"Agent not found: {agent_id}")
        return self.update(replace(agent, enabled=True))

    def disable(
        self, agent_id: str, *, owner_id: str, workspace_id: str, project_id: str
    ) -> Agent:
        agent = self.get_by_id(
            agent_id,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if agent is None:
            raise ValueError(f"Agent not found: {agent_id}")
        return self.update(replace(agent, enabled=False))

    def list_versions(self, agent_id: str) -> list[AgentVersion]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM agent_versions
                WHERE agent_id = ?
                ORDER BY version_number DESC
                """,
                (agent_id,),
            ).fetchall()
        versions: list[AgentVersion] = []
        for row in rows:
            versions.append(
                AgentVersion(
                    id=str(row["id"]),
                    agent_id=str(row["agent_id"]),
                    version_number=int(row["version_number"]),
                    change_summary=str(row["change_summary"]),
                    snapshot=dict(self._parse_json(row["snapshot_json"], {})),
                    created_at=datetime.fromisoformat(str(row["created_at"])),
                )
            )
        return versions

    def get_version(self, version_id: str) -> AgentVersion | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM agent_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
        if row is None:
            return None
        return AgentVersion(
            id=str(row["id"]),
            agent_id=str(row["agent_id"]),
            version_number=int(row["version_number"]),
            change_summary=str(row["change_summary"]),
            snapshot=dict(self._parse_json(row["snapshot_json"], {})),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def get_latest_version_number(self, agent_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) AS version_number
                FROM agent_versions
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["version_number"] or 0)

    def create_version(self, version: AgentVersion) -> AgentVersion:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agent_versions (
                    id, agent_id, version_number, change_summary, snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    version.id,
                    version.agent_id,
                    version.version_number,
                    version.change_summary,
                    json.dumps(version.snapshot),
                    version.created_at.isoformat(),
                ),
            )
            self._connection.commit()
        return version

    def list_test_runs(self, agent_id: str) -> list[AgentTestRun]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM agent_test_runs
                WHERE agent_id = ?
                ORDER BY created_at DESC
                """,
                (agent_id,),
            ).fetchall()
        test_runs: list[AgentTestRun] = []
        for row in rows:
            test_runs.append(
                AgentTestRun(
                    id=str(row["id"]),
                    agent_id=str(row["agent_id"]),
                    prompt=str(row["prompt"]),
                    reasoning=str(row["reasoning"]),
                    tool_calls=list(self._parse_json(row["tool_calls_json"], [])),
                    execution=list(self._parse_json(row["execution_json"], [])),
                    final_answer=str(row["final_answer"]),
                    success=bool(int(row["success"])),
                    error=str(row["error"]) if row["error"] else None,
                    timing_ms=float(row["timing_ms"]),
                    created_at=datetime.fromisoformat(str(row["created_at"])),
                )
            )
        return test_runs

    def get_test_run(self, test_run_id: str) -> AgentTestRun | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM agent_test_runs WHERE id = ?",
                (test_run_id,),
            ).fetchone()
        if row is None:
            return None
        return AgentTestRun(
            id=str(row["id"]),
            agent_id=str(row["agent_id"]),
            prompt=str(row["prompt"]),
            reasoning=str(row["reasoning"]),
            tool_calls=list(self._parse_json(row["tool_calls_json"], [])),
            execution=list(self._parse_json(row["execution_json"], [])),
            final_answer=str(row["final_answer"]),
            success=bool(int(row["success"])),
            error=str(row["error"]) if row["error"] else None,
            timing_ms=float(row["timing_ms"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def create_test_run(self, test_run: AgentTestRun) -> AgentTestRun:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agent_test_runs (
                    id, agent_id, prompt, reasoning, tool_calls_json, execution_json,
                    final_answer, success, error, timing_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    test_run.id,
                    test_run.agent_id,
                    test_run.prompt,
                    test_run.reasoning,
                    json.dumps(test_run.tool_calls),
                    json.dumps(test_run.execution),
                    test_run.final_answer,
                    self._bool(test_run.success),
                    test_run.error,
                    test_run.timing_ms,
                    test_run.created_at.isoformat(),
                ),
            )
            self._connection.commit()
        return test_run

    def dashboard_metrics(self, agent_id: str) -> dict[str, Any]:
        versions = self.list_versions(agent_id)
        test_runs = self.list_test_runs(agent_id)
        if test_runs:
            last_run = test_runs[0].created_at
            success_count = sum(1 for item in test_runs if item.success)
            average_runtime = sum(item.timing_ms for item in test_runs) / len(test_runs)
        else:
            last_run = None
            success_count = 0
            average_runtime = 0.0
        success_rate = (success_count / len(test_runs)) if test_runs else 0.0
        agent = self.get_by_id(
            agent_id,
            owner_id=self._get_agent_scope(agent_id, "owner_id"),
            workspace_id=self._get_agent_scope(agent_id, "workspace_id"),
            project_id=self._get_agent_scope(agent_id, "project_id"),
        )
        memory_usage = "0 modes"
        knowledge_source_count = 0
        connected_agent_count = 0
        status = "unknown"
        if agent is not None:
            memory_modes = [
                agent.agent_memory_enabled,
                agent.project_memory_enabled,
                agent.long_term_memory_enabled,
                agent.conversation_memory_enabled,
            ]
            memory_usage = f"{sum(1 for mode in memory_modes if mode)} modes"
            knowledge_source_count = (
                len(agent.knowledge_source_ids)
                + len(agent.document_library_ids)
                + len(agent.github_repositories)
                + len(agent.sharepoint_sites)
                + len(agent.uploaded_document_ids)
            )
            connected_agent_count = len(agent.connected_agent_ids)
            status = "enabled" if agent.enabled else "disabled"
        return {
            "agent_id": agent_id,
            "status": status,
            "last_run_at": last_run,
            "success_rate": success_rate,
            "average_runtime_ms": average_runtime,
            "memory_usage": memory_usage,
            "knowledge_source_count": knowledge_source_count,
            "connected_agent_count": connected_agent_count,
            "total_versions": len(versions),
        }

    def _get_agent_scope(self, agent_id: str, field_name: str) -> str:
        with self._lock:
            row = self._connection.execute(
                f"SELECT {field_name} FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
        if row is None:
            return "default"
        return str(row[field_name])
