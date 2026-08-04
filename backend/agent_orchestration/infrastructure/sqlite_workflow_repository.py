"""SQLite repository for orchestration workflows and run history."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agent_orchestration.domain.run import (
    AgentMessage,
    NodeExecutionRecord,
    WorkflowRun,
)
from backend.agent_orchestration.domain.workflow import Workflow
from backend.agent_orchestration.repository.workflow_repository import (
    WorkflowRepository,
)
from backend.database.sqlite_connection import create_sqlite_connection


class SQLiteWorkflowRepository(WorkflowRepository):
    """SQLite-backed workflow repository."""

    def __init__(self, db_path: str = "data/agent_orchestration/workflows.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS orchestration_workflows (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS orchestration_workflow_versions (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    change_summary TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS orchestration_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_payload_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    duration_ms REAL NOT NULL,
                    error TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    pending_node_id TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL,
                    node_records_json TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL,
                    logs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self._connection.commit()

    def create_workflow(self, workflow: Workflow) -> Workflow:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO orchestration_workflows (
                    id, owner_id, workspace_id, project_id, name, description,
                    enabled, version, snapshot_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow.id,
                    workflow.owner_id,
                    workflow.workspace_id,
                    workflow.project_id,
                    workflow.name,
                    workflow.description,
                    1 if workflow.enabled else 0,
                    workflow.version,
                    json.dumps(workflow.to_snapshot()),
                    workflow.created_at.isoformat(),
                    workflow.updated_at.isoformat(),
                ),
            )
            self._connection.commit()
        return workflow

    def update_workflow(self, workflow: Workflow) -> Workflow:
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE orchestration_workflows
                SET name = ?, description = ?, enabled = ?, version = ?,
                    snapshot_json = ?, updated_at = ?
                WHERE id = ? AND owner_id = ? AND workspace_id = ? AND project_id = ?
                """,
                (
                    workflow.name,
                    workflow.description,
                    1 if workflow.enabled else 0,
                    workflow.version,
                    json.dumps(workflow.to_snapshot()),
                    workflow.updated_at.isoformat(),
                    workflow.id,
                    workflow.owner_id,
                    workflow.workspace_id,
                    workflow.project_id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Workflow not found: {workflow.id}")
        return workflow

    def delete_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM orchestration_workflows
                WHERE id = ? AND owner_id = ? AND workspace_id = ? AND project_id = ?
                """,
                (workflow_id, owner_id, workspace_id, project_id),
            )
            self._connection.execute(
                "DELETE FROM orchestration_workflow_versions WHERE workflow_id = ?",
                (workflow_id,),
            )
            self._connection.execute(
                "DELETE FROM orchestration_runs WHERE workflow_id = ?",
                (workflow_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_workflow(
        self,
        workflow_id: str,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> Workflow | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT snapshot_json
                FROM orchestration_workflows
                WHERE id = ? AND owner_id = ? AND workspace_id = ? AND project_id = ?
                """,
                (workflow_id, owner_id, workspace_id, project_id),
            ).fetchone()
        if row is None:
            return None
        payload = self._parse_json(str(row["snapshot_json"]), {})
        if not isinstance(payload, dict):
            return None
        return Workflow.from_snapshot(payload)

    def list_workflows(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> list[Workflow]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT snapshot_json
                FROM orchestration_workflows
                WHERE owner_id = ? AND workspace_id = ? AND project_id = ?
                ORDER BY updated_at DESC
                """,
                (owner_id, workspace_id, project_id),
            ).fetchall()
        workflows: list[Workflow] = []
        for row in rows:
            payload = self._parse_json(str(row["snapshot_json"]), {})
            if isinstance(payload, dict):
                workflows.append(Workflow.from_snapshot(payload))
        return workflows

    def list_workflow_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, workflow_id, version_number, change_summary, snapshot_json, created_at
                FROM orchestration_workflow_versions
                WHERE workflow_id = ?
                ORDER BY version_number DESC
                """,
                (workflow_id,),
            ).fetchall()
        versions: list[dict[str, Any]] = []
        for row in rows:
            versions.append(
                {
                    "id": str(row["id"]),
                    "workflow_id": str(row["workflow_id"]),
                    "version_number": int(row["version_number"]),
                    "change_summary": str(row["change_summary"]),
                    "snapshot": dict(self._parse_json(str(row["snapshot_json"]), {})),
                    "created_at": datetime.fromisoformat(str(row["created_at"])),
                }
            )
        return versions

    def create_workflow_version(
        self,
        workflow_id: str,
        *,
        version_number: int,
        change_summary: str,
        snapshot: dict[str, Any],
    ) -> None:
        version_id = f"{workflow_id}:v{version_number}"
        created_at = datetime.now(UTC).isoformat()
        with self._lock:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO orchestration_workflow_versions (
                    id, workflow_id, version_number, change_summary, snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    workflow_id,
                    version_number,
                    change_summary,
                    json.dumps(snapshot),
                    created_at,
                ),
            )
            self._connection.commit()

    def get_latest_workflow_version_number(self, workflow_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) AS max_version
                FROM orchestration_workflow_versions
                WHERE workflow_id = ?
                """,
                (workflow_id,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["max_version"])

    def create_run(self, run: WorkflowRun) -> WorkflowRun:
        scope = self._workflow_scope(run.workflow_id)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO orchestration_runs (
                    id, workflow_id, owner_id, workspace_id, project_id, status,
                    input_payload_json, context_json, started_at, ended_at, duration_ms, error,
                    current_node_id, pending_node_id, cancel_requested,
                    node_records_json, messages_json, artifacts_json, logs_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._serialize_run(run, scope),
            )
            self._connection.commit()
        return run

    def update_run(self, run: WorkflowRun) -> WorkflowRun:
        scope = self._workflow_scope(run.workflow_id)
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE orchestration_runs
                SET status = ?,
                    input_payload_json = ?,
                    context_json = ?,
                    started_at = ?,
                    ended_at = ?,
                    duration_ms = ?,
                    error = ?,
                    current_node_id = ?,
                    pending_node_id = ?,
                    cancel_requested = ?,
                    node_records_json = ?,
                    messages_json = ?,
                    artifacts_json = ?,
                    logs_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                self._serialize_run_update(run, scope),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Run not found: {run.id}")
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM orchestration_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_run(row)

    def list_runs(self, workflow_id: str) -> list[WorkflowRun]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM orchestration_runs
                WHERE workflow_id = ?
                ORDER BY created_at DESC
                """,
                (workflow_id,),
            ).fetchall()
        return [
            run for run in (self._row_to_run(row) for row in rows) if run is not None
        ]

    def list_recent_runs(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        limit: int,
    ) -> list[WorkflowRun]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM orchestration_runs
                WHERE owner_id = ? AND workspace_id = ? AND project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (owner_id, workspace_id, project_id, max(1, limit)),
            ).fetchall()
        return [
            run for run in (self._row_to_run(row) for row in rows) if run is not None
        ]

    def dashboard_metrics(
        self,
        *,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        runs = self.list_recent_runs(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            limit=500,
        )
        total_runtime = sum(run.duration_ms for run in runs if run.duration_ms > 0)
        durations = [run.duration_ms for run in runs if run.duration_ms > 0]
        agent_usage: dict[str, int] = {}
        workflow_hits: dict[str, int] = {}
        for run in runs:
            workflow_hits[run.workflow_id] = workflow_hits.get(run.workflow_id, 0) + 1
            for message in run.messages:
                key = message.receiver or "unknown"
                agent_usage[key] = agent_usage.get(key, 0) + 1

        return {
            "running": sum(1 for run in runs if run.status == "running"),
            "queued": sum(1 for run in runs if run.status == "queued"),
            "succeeded": sum(1 for run in runs if run.status == "succeeded"),
            "failed": sum(1 for run in runs if run.status == "failed"),
            "average_runtime_ms": total_runtime / len(durations) if durations else 0.0,
            "average_token_usage": 0.0,
            "agent_usage": agent_usage,
            "most_active_workflows": [
                {"workflow_id": workflow_id, "runs": count}
                for workflow_id, count in sorted(
                    workflow_hits.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:5]
            ],
        }

    @staticmethod
    def _parse_json(payload: str, default: Any) -> Any:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return default

    def _workflow_scope(self, workflow_id: str) -> tuple[str, str, str]:
        row = self._connection.execute(
            """
            SELECT owner_id, workspace_id, project_id
            FROM orchestration_workflows
            WHERE id = ?
            """,
            (workflow_id,),
        ).fetchone()
        if row is None:
            return ("anonymous", "default", "default")
        return (str(row["owner_id"]), str(row["workspace_id"]), str(row["project_id"]))

    def _serialize_run(
        self, run: WorkflowRun, scope: tuple[str, str, str]
    ) -> tuple[Any, ...]:
        owner_id, workspace_id, project_id = scope
        return (
            run.id,
            run.workflow_id,
            owner_id,
            workspace_id,
            project_id,
            run.status,
            json.dumps(run.input_payload),
            json.dumps(run.context),
            run.started_at.isoformat() if run.started_at else None,
            run.ended_at.isoformat() if run.ended_at else None,
            run.duration_ms,
            run.error,
            run.current_node_id,
            run.pending_node_id,
            1 if run.cancel_requested else 0,
            json.dumps(
                [self._serialize_node_record(item) for item in run.node_records]
            ),
            json.dumps([self._serialize_message(item) for item in run.messages]),
            json.dumps(run.artifacts),
            json.dumps(run.logs),
            run.created_at.isoformat(),
            run.updated_at.isoformat(),
        )

    def _serialize_run_update(
        self,
        run: WorkflowRun,
        scope: tuple[str, str, str],
    ) -> tuple[Any, ...]:
        _ = scope
        return (
            run.status,
            json.dumps(run.input_payload),
            json.dumps(run.context),
            run.started_at.isoformat() if run.started_at else None,
            run.ended_at.isoformat() if run.ended_at else None,
            run.duration_ms,
            run.error,
            run.current_node_id,
            run.pending_node_id,
            1 if run.cancel_requested else 0,
            json.dumps(
                [self._serialize_node_record(item) for item in run.node_records]
            ),
            json.dumps([self._serialize_message(item) for item in run.messages]),
            json.dumps(run.artifacts),
            json.dumps(run.logs),
            run.updated_at.isoformat(),
            run.id,
        )

    @staticmethod
    def _serialize_node_record(record: NodeExecutionRecord) -> dict[str, Any]:
        return {
            "node_id": record.node_id,
            "node_name": record.node_name,
            "node_type": record.node_type,
            "status": record.status,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "completed_at": (
                record.completed_at.isoformat() if record.completed_at else None
            ),
            "duration_ms": record.duration_ms,
            "error": record.error,
            "output": dict(record.output),
        }

    @staticmethod
    def _serialize_message(message: AgentMessage) -> dict[str, Any]:
        return {
            "message_id": message.message_id,
            "sender": message.sender,
            "receiver": message.receiver,
            "timestamp": message.timestamp.isoformat(),
            "conversation_id": message.conversation_id,
            "workflow_id": message.workflow_id,
            "execution_id": message.execution_id,
            "sender_agent": message.sender_agent,
            "receiver_agent": message.receiver_agent,
            "task_id": message.task_id,
            "priority": message.priority,
            "message_type": message.message_type,
            "thought": message.thought,
            "reasoning_summary": message.reasoning_summary,
            "payload": dict(message.payload),
            "reasoning": message.reasoning,
            "attachments": [dict(item) for item in message.attachments],
            "artifacts": [dict(item) for item in message.artifacts],
            "tool_outputs": [dict(item) for item in message.tool_outputs],
            "memory_references": [dict(item) for item in message.memory_references],
            "confidence": message.confidence,
            "metadata": dict(message.metadata),
        }

    def _row_to_run(self, row: sqlite3.Row | None) -> WorkflowRun | None:
        if row is None:
            return None
        node_records_raw = self._parse_json(str(row["node_records_json"]), [])
        messages_raw = self._parse_json(str(row["messages_json"]), [])
        node_records = [
            NodeExecutionRecord(
                node_id=str(item.get("node_id", "")),
                node_name=str(item.get("node_name", "")),
                node_type=str(item.get("node_type", "")),
                status=str(item.get("status", "pending")),
                started_at=(
                    datetime.fromisoformat(str(item.get("started_at")))
                    if item.get("started_at")
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(str(item.get("completed_at")))
                    if item.get("completed_at")
                    else None
                ),
                duration_ms=float(item.get("duration_ms", 0.0)),
                error=str(item.get("error", "")),
                output=dict(item.get("output", {})),
            )
            for item in node_records_raw
            if isinstance(item, dict)
        ]
        messages = [
            AgentMessage(
                message_id=str(item.get("message_id", "")),
                sender=str(item.get("sender", "")),
                receiver=str(item.get("receiver", "")),
                timestamp=datetime.fromisoformat(str(item.get("timestamp"))),
                conversation_id=str(item.get("conversation_id", "")),
                workflow_id=str(item.get("workflow_id", "")),
                execution_id=str(item.get("execution_id", "")),
                sender_agent=str(item.get("sender_agent", "")),
                receiver_agent=str(item.get("receiver_agent", "")),
                task_id=str(item.get("task_id", "")),
                priority=str(item.get("priority", "normal")),
                message_type=str(item.get("message_type", "StatusUpdate")),
                thought=str(item.get("thought", "")),
                reasoning_summary=str(item.get("reasoning_summary", "")),
                payload=dict(item.get("payload", {})),
                reasoning=str(item.get("reasoning", "")),
                attachments=[
                    dict(attachment)
                    for attachment in item.get("attachments", [])
                    if isinstance(attachment, dict)
                ],
                artifacts=[
                    dict(artifact)
                    for artifact in item.get("artifacts", [])
                    if isinstance(artifact, dict)
                ],
                tool_outputs=[
                    dict(tool_output)
                    for tool_output in item.get("tool_outputs", [])
                    if isinstance(tool_output, dict)
                ],
                memory_references=[
                    dict(reference)
                    for reference in item.get("memory_references", [])
                    if isinstance(reference, dict)
                ],
                confidence=float(item.get("confidence", 0.0) or 0.0),
                metadata=dict(item.get("metadata", {})),
            )
            for item in messages_raw
            if isinstance(item, dict) and item.get("timestamp")
        ]
        return WorkflowRun(
            id=str(row["id"]),
            workflow_id=str(row["workflow_id"]),
            status=str(row["status"]),
            input_payload=dict(self._parse_json(str(row["input_payload_json"]), {})),
            context=dict(self._parse_json(str(row["context_json"]), {})),
            started_at=(
                datetime.fromisoformat(str(row["started_at"]))
                if row["started_at"]
                else None
            ),
            ended_at=(
                datetime.fromisoformat(str(row["ended_at"]))
                if row["ended_at"]
                else None
            ),
            duration_ms=float(row["duration_ms"]),
            error=str(row["error"]),
            current_node_id=str(row["current_node_id"]),
            pending_node_id=str(row["pending_node_id"]),
            cancel_requested=bool(int(row["cancel_requested"])),
            node_records=node_records,
            messages=messages,
            artifacts=list(self._parse_json(str(row["artifacts_json"]), [])),
            logs=list(self._parse_json(str(row["logs_json"]), [])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
