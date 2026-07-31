"""SQLite repository for Agent Studio agents."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from backend.agent_studio.domain.entities.agent import Agent
from backend.agent_studio.repository.agent_repository import AgentRepository
from backend.database.sqlite_connection import create_sqlite_connection


class SQLiteAgentRepository(AgentRepository):
    """SQLite-backed Agent Studio repository."""

    def __init__(self, db_path: str = "data/agent_studio/agent_studio.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
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
            placeholder_tables = {
                "agent_workflows": "agent_id TEXT NOT NULL",
                "agent_tools": "agent_id TEXT NOT NULL",
                "agent_runs": "agent_id TEXT NOT NULL",
                "agent_messages": "agent_id TEXT NOT NULL",
                "agent_templates": "agent_id TEXT NOT NULL",
            }
            for table_name, extra_columns in placeholder_tables.items():
                self._connection.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id TEXT PRIMARY KEY,
                        {extra_columns},
                        created_at TEXT NOT NULL
                    )
                    """)
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create(self, agent: Agent) -> Agent:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agents (
                    id, name, description, role, objective, system_prompt,
                    enabled, short_term_enabled, long_term_enabled,
                    project_memory_enabled, tools_allowed, connectors_allowed,
                    approval_required, max_iterations, timeout, retry_policy,
                    tags, owner_id, workspace_id, project_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._serialize(agent),
            )
            self._connection.commit()
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
                    tags = ?, owner_id = ?, workspace_id = ?, project_id = ?, updated_at = ?
                WHERE id = ?
                  AND owner_id = ?
                  AND workspace_id = ?
                  AND project_id = ?
                """,
                (
                    updated.name,
                    updated.description,
                    updated.role,
                    updated.objective,
                    updated.system_prompt,
                    1 if updated.enabled else 0,
                    1 if updated.short_term_enabled else 0,
                    1 if updated.long_term_enabled else 0,
                    1 if updated.project_memory_enabled else 0,
                    json.dumps(updated.tools_allowed),
                    json.dumps(updated.connectors_allowed),
                    1 if updated.approval_required else 0,
                    updated.max_iterations,
                    updated.timeout,
                    json.dumps(updated.retry_policy),
                    json.dumps(updated.tags),
                    updated.owner_id,
                    updated.workspace_id,
                    updated.project_id,
                    updated.updated_at.isoformat(),
                    updated.id,
                    updated.owner_id,
                    updated.workspace_id,
                    updated.project_id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Agent not found: {updated.id}")
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
                ORDER BY created_at DESC
                """,
                (owner_id, workspace_id, project_id),
            ).fetchall()
        agents: list[Agent] = []
        for row in rows:
            agent = self._row_to_agent(row)
            if agent is not None:
                agents.append(agent)
        return agents

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

    def _serialize(self, agent: Agent) -> tuple[object, ...]:
        return (
            agent.id,
            agent.name,
            agent.description,
            agent.role,
            agent.objective,
            agent.system_prompt,
            1 if agent.enabled else 0,
            1 if agent.short_term_enabled else 0,
            1 if agent.long_term_enabled else 0,
            1 if agent.project_memory_enabled else 0,
            json.dumps(agent.tools_allowed),
            json.dumps(agent.connectors_allowed),
            1 if agent.approval_required else 0,
            agent.max_iterations,
            agent.timeout,
            json.dumps(agent.retry_policy),
            json.dumps(agent.tags),
            agent.owner_id,
            agent.workspace_id,
            agent.project_id,
            agent.created_at.isoformat(),
            agent.updated_at.isoformat(),
        )

    @staticmethod
    def _row_to_agent(row: sqlite3.Row | None) -> Agent | None:
        if row is None:
            return None
        return Agent(
            id=str(row["id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            role=str(row["role"]),
            objective=str(row["objective"]),
            system_prompt=str(row["system_prompt"]),
            enabled=bool(int(row["enabled"])),
            short_term_enabled=bool(int(row["short_term_enabled"])),
            long_term_enabled=bool(int(row["long_term_enabled"])),
            project_memory_enabled=bool(int(row["project_memory_enabled"])),
            tools_allowed=list(json.loads(str(row["tools_allowed"]))),
            connectors_allowed=list(json.loads(str(row["connectors_allowed"]))),
            approval_required=bool(int(row["approval_required"])),
            max_iterations=int(row["max_iterations"]),
            timeout=int(row["timeout"]),
            retry_policy=dict(json.loads(str(row["retry_policy"]))),
            tags=list(json.loads(str(row["tags"]))),
            owner_id=str(row["owner_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
