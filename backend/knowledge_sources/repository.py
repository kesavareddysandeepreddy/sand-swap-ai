"""SQLite persistence for knowledge sources."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from backend.database.sqlite_connection import create_sqlite_connection
from backend.knowledge_sources.models import KnowledgeSource
from backend.knowledge_sources.source_types import SourceType


class KnowledgeSourceRepository:
    """SQLite-backed repository implementation for knowledge sources."""

    def __init__(self, db_path: str = "data/enterprise/enterprise.db") -> None:
        if db_path == ":memory:" or db_path.startswith("file:"):
            self.db_path = db_path
        else:
            self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    connection_config TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    embedding_count INTEGER NOT NULL,
                    last_sync TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_sources_project ON knowledge_sources (project_id)"
            )
            self._connection.commit()

    def add(self, source: KnowledgeSource) -> KnowledgeSource:
        """Persist a new source."""
        with self._lock:
            now = datetime.now(UTC)
            stored = KnowledgeSource(
                id=source.id,
                project_id=source.project_id,
                name=source.name,
                source_type=source.source_type,
                connection_config=dict(source.connection_config),
                enabled=source.enabled,
                status=source.status,
                file_count=source.file_count,
                chunk_count=source.chunk_count,
                embedding_count=source.embedding_count,
                last_sync=source.last_sync,
                metadata=dict(source.metadata),
                created_at=now,
                updated_at=now,
            )
            self._connection.execute(
                """
                INSERT INTO knowledge_sources (
                    id, project_id, name, source_type,
                    connection_config, enabled, status,
                    file_count, chunk_count, embedding_count,
                    last_sync, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(stored),
            )
            self._connection.commit()
        return stored

    def update(self, source: KnowledgeSource) -> KnowledgeSource:
        """Persist source updates."""
        with self._lock:
            existing = self.get(source.id)
            if existing is None:
                raise KeyError(f"Knowledge source '{source.id}' not found")
            stored = KnowledgeSource(
                id=source.id,
                project_id=source.project_id,
                name=source.name,
                source_type=source.source_type,
                connection_config=dict(source.connection_config),
                enabled=source.enabled,
                status=source.status,
                file_count=source.file_count,
                chunk_count=source.chunk_count,
                embedding_count=source.embedding_count,
                last_sync=source.last_sync,
                metadata=dict(source.metadata),
                created_at=existing.created_at,
                updated_at=datetime.now(UTC),
            )
            self._connection.execute(
                """
                UPDATE knowledge_sources
                SET project_id = ?,
                    name = ?,
                    source_type = ?,
                    connection_config = ?,
                    enabled = ?,
                    status = ?,
                    file_count = ?,
                    chunk_count = ?,
                    embedding_count = ?,
                    last_sync = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                self._to_update_row(stored),
            )
            self._connection.commit()
        return stored

    def delete(self, source_id: str) -> bool:
        """Delete a source by id."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM knowledge_sources WHERE id = ?",
                (source_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get(self, source_id: str) -> KnowledgeSource | None:
        """Get one source by id."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM knowledge_sources WHERE id = ?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def list(self, project_id: str) -> list[KnowledgeSource]:
        """List sources for one project."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM knowledge_sources
                WHERE project_id = ?
                ORDER BY created_at ASC
                """,
                (project_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def enable(self, source_id: str) -> KnowledgeSource:
        """Enable a source."""
        source = self.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")
        source.enabled = True
        return self.update(source)

    def disable(self, source_id: str) -> KnowledgeSource:
        """Disable a source."""
        source = self.get(source_id)
        if source is None:
            raise KeyError(f"Knowledge source '{source_id}' not found")
        source.enabled = False
        return self.update(source)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _to_row(self, source: KnowledgeSource) -> tuple[object, ...]:
        return (
            source.id,
            source.project_id,
            source.name,
            source.source_type.value,
            json.dumps(source.connection_config, sort_keys=True),
            1 if source.enabled else 0,
            source.status,
            int(source.file_count),
            int(source.chunk_count),
            int(source.embedding_count),
            source.last_sync.isoformat() if source.last_sync else None,
            json.dumps(source.metadata, sort_keys=True),
            source.created_at.isoformat(),
            source.updated_at.isoformat(),
        )

    def _to_update_row(self, source: KnowledgeSource) -> tuple[object, ...]:
        return (
            source.project_id,
            source.name,
            source.source_type.value,
            json.dumps(source.connection_config, sort_keys=True),
            1 if source.enabled else 0,
            source.status,
            int(source.file_count),
            int(source.chunk_count),
            int(source.embedding_count),
            source.last_sync.isoformat() if source.last_sync else None,
            json.dumps(source.metadata, sort_keys=True),
            source.updated_at.isoformat(),
            source.id,
        )

    def _from_row(self, row: sqlite3.Row) -> KnowledgeSource:
        raw_last_sync = row["last_sync"]
        last_sync = (
            datetime.fromisoformat(str(raw_last_sync)) if raw_last_sync else None
        )
        return KnowledgeSource(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            name=str(row["name"]),
            source_type=SourceType(str(row["source_type"])),
            connection_config=self._loads_json(str(row["connection_config"])),
            enabled=bool(int(row["enabled"])),
            status=str(row["status"]),
            file_count=int(row["file_count"]),
            chunk_count=int(row["chunk_count"]),
            embedding_count=int(row["embedding_count"]),
            last_sync=last_sync,
            metadata=self._loads_json(str(row["metadata"])),
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
