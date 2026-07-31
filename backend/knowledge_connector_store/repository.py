"""SQLite repository for persistent connector store records."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from backend.database.sqlite_connection import create_sqlite_connection
from backend.knowledge_connector_store.models import (
    ConnectorConfiguration,
    ConnectorCredentials,
    ConnectorRecord,
    ConnectorStatistics,
    ConnectorSyncState,
)
from backend.knowledge_sources.source_types import SourceType


class ConnectorStoreRepository:
    """Persistence repository for connector records, sync state, and statistics."""

    def __init__(self, db_path: str = "data/enterprise/enterprise.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS connector_store_records (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    credentials_reference TEXT NOT NULL,
                    credentials_encrypted_payload TEXT NOT NULL,
                    credentials_provider TEXT NOT NULL,
                    credentials_metadata TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    configuration_settings TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    sync_last_sync_at TEXT,
                    sync_last_incremental_sync_at TEXT,
                    sync_cursor TEXT NOT NULL,
                    sync_metadata TEXT NOT NULL,
                    stats_files_indexed INTEGER NOT NULL,
                    stats_chunks_indexed INTEGER NOT NULL,
                    stats_embeddings_indexed INTEGER NOT NULL,
                    stats_errors_count INTEGER NOT NULL,
                    stats_metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self._connection.commit()
            self._ensure_column("connector_store_records", "source_id", "TEXT")

    def _ensure_column(
        self, table_name: str, column_name: str, column_sql: str
    ) -> None:
        rows = self._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {str(row[1]) for row in rows}
        if column_name in existing_columns:
            return
        self._connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )
        self._connection.commit()

    def create(self, record: ConnectorRecord) -> ConnectorRecord:
        with self._lock:
            now = datetime.now(UTC)
            stored = ConnectorRecord(
                id=record.id,
                source_id=record.source_id,
                source_type=record.source_type,
                name=record.name,
                credentials=record.credentials,
                configuration=record.configuration,
                sync_state=record.sync_state,
                statistics=record.statistics,
                enabled=record.enabled,
                created_at=now,
                updated_at=now,
            )
            self._connection.execute(
                """
                INSERT INTO connector_store_records (
                    id, source_id, source_type, name, enabled,
                    credentials_reference, credentials_encrypted_payload, credentials_provider, credentials_metadata,
                    workspace_id, project_id, configuration_settings,
                    sync_status, sync_last_sync_at, sync_last_incremental_sync_at, sync_cursor, sync_metadata,
                    stats_files_indexed, stats_chunks_indexed, stats_embeddings_indexed, stats_errors_count, stats_metadata,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(stored),
            )
            self._connection.commit()
        return stored

    def update(self, record: ConnectorRecord) -> ConnectorRecord:
        with self._lock:
            now = datetime.now(UTC)
            existing = self.get(record.id)
            if existing is None:
                raise KeyError(f"Connector record '{record.id}' not found")
            stored = ConnectorRecord(
                id=record.id,
                source_id=record.source_id,
                source_type=record.source_type,
                name=record.name,
                credentials=record.credentials,
                configuration=record.configuration,
                sync_state=record.sync_state,
                statistics=record.statistics,
                enabled=record.enabled,
                created_at=existing.created_at,
                updated_at=now,
            )
            self._connection.execute(
                """
                UPDATE connector_store_records
                SET source_type = ?,
                    source_id = ?,
                    name = ?,
                    enabled = ?,
                    credentials_reference = ?,
                    credentials_encrypted_payload = ?,
                    credentials_provider = ?,
                    credentials_metadata = ?,
                    workspace_id = ?,
                    project_id = ?,
                    configuration_settings = ?,
                    sync_status = ?,
                    sync_last_sync_at = ?,
                    sync_last_incremental_sync_at = ?,
                    sync_cursor = ?,
                    sync_metadata = ?,
                    stats_files_indexed = ?,
                    stats_chunks_indexed = ?,
                    stats_embeddings_indexed = ?,
                    stats_errors_count = ?,
                    stats_metadata = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                self._to_update_row(stored),
            )
            self._connection.commit()
        return stored

    def get(self, record_id: str) -> ConnectorRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM connector_store_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def delete(self, record_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM connector_store_records WHERE id = ?",
                (record_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def list_by_project(self, *, project_id: str) -> list[ConnectorRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM connector_store_records
                WHERE project_id = ?
                ORDER BY created_at ASC
                """,
                (project_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_all(self) -> list[ConnectorRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM connector_store_records ORDER BY created_at ASC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _to_row(self, record: ConnectorRecord) -> tuple[object, ...]:
        return (
            record.id,
            record.source_id,
            record.source_type.value,
            record.name,
            1 if record.enabled else 0,
            record.credentials.reference,
            record.credentials.encrypted_payload,
            record.credentials.provider,
            json.dumps(record.credentials.metadata, sort_keys=True),
            record.configuration.workspace_id,
            record.configuration.project_id,
            json.dumps(record.configuration.settings, sort_keys=True),
            record.sync_state.status,
            (
                record.sync_state.last_sync_at.isoformat()
                if record.sync_state.last_sync_at is not None
                else None
            ),
            (
                record.sync_state.last_incremental_sync_at.isoformat()
                if record.sync_state.last_incremental_sync_at is not None
                else None
            ),
            record.sync_state.cursor,
            json.dumps(record.sync_state.metadata, sort_keys=True),
            int(record.statistics.files_indexed),
            int(record.statistics.chunks_indexed),
            int(record.statistics.embeddings_indexed),
            int(record.statistics.errors_count),
            json.dumps(record.statistics.metadata, sort_keys=True),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    def _to_update_row(self, record: ConnectorRecord) -> tuple[object, ...]:
        return (
            record.source_type.value,
            record.source_id,
            record.name,
            1 if record.enabled else 0,
            record.credentials.reference,
            record.credentials.encrypted_payload,
            record.credentials.provider,
            json.dumps(record.credentials.metadata, sort_keys=True),
            record.configuration.workspace_id,
            record.configuration.project_id,
            json.dumps(record.configuration.settings, sort_keys=True),
            record.sync_state.status,
            (
                record.sync_state.last_sync_at.isoformat()
                if record.sync_state.last_sync_at is not None
                else None
            ),
            (
                record.sync_state.last_incremental_sync_at.isoformat()
                if record.sync_state.last_incremental_sync_at is not None
                else None
            ),
            record.sync_state.cursor,
            json.dumps(record.sync_state.metadata, sort_keys=True),
            int(record.statistics.files_indexed),
            int(record.statistics.chunks_indexed),
            int(record.statistics.embeddings_indexed),
            int(record.statistics.errors_count),
            json.dumps(record.statistics.metadata, sort_keys=True),
            record.updated_at.isoformat(),
            record.id,
        )

    def _from_row(self, row: sqlite3.Row) -> ConnectorRecord:
        return ConnectorRecord(
            id=str(row["id"]),
            source_id=str(row["source_id"] or ""),
            source_type=SourceType(str(row["source_type"])),
            name=str(row["name"]),
            enabled=bool(int(row["enabled"])),
            credentials=ConnectorCredentials(
                reference=str(row["credentials_reference"]),
                encrypted_payload=str(row["credentials_encrypted_payload"]),
                provider=str(row["credentials_provider"]),
                metadata=self._loads_json(str(row["credentials_metadata"])),
            ),
            configuration=ConnectorConfiguration(
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
                settings=self._loads_json(str(row["configuration_settings"])),
            ),
            sync_state=ConnectorSyncState(
                status=str(row["sync_status"]),
                last_sync_at=self._parse_datetime(row["sync_last_sync_at"]),
                last_incremental_sync_at=self._parse_datetime(
                    row["sync_last_incremental_sync_at"]
                ),
                cursor=str(row["sync_cursor"]),
                metadata=self._loads_json(str(row["sync_metadata"])),
            ),
            statistics=ConnectorStatistics(
                files_indexed=int(row["stats_files_indexed"]),
                chunks_indexed=int(row["stats_chunks_indexed"]),
                embeddings_indexed=int(row["stats_embeddings_indexed"]),
                errors_count=int(row["stats_errors_count"]),
                metadata=self._loads_json(str(row["stats_metadata"])),
            ),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    @staticmethod
    def _loads_json(raw: str) -> dict[str, object]:
        if not raw:
            return {}
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
        return {}

    @staticmethod
    def _parse_datetime(raw: object) -> datetime | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        return datetime.fromisoformat(text)
