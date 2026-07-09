"""
SandSwap AI - SQLite Memory Store
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from backend.core.logging.logger import LoggerFactory
from backend.memory.models.memory_record import MemoryRecord
from backend.memory.stores.base_store import BaseMemoryStore


class SQLiteMemoryStore(BaseMemoryStore):
    def __init__(self, db_path: str = "data/memory/memory.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self.logger = LoggerFactory.get_logger("SQLiteMemoryStore")
        self.logger.info("SQLite database path: %s", self.db_path)
        self._lock = threading.RLock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories(
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    project_id TEXT,
                    conversation_id TEXT,
                    memory_type TEXT,
                    category TEXT,
                    memory_key TEXT,
                    memory_value TEXT,
                    summary TEXT,
                    importance REAL,
                    confidence REAL,
                    source TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    last_accessed TEXT,
                    access_count INTEGER,
                    expires_at TEXT,
                    embedding_id TEXT,
                    parent_memory_id TEXT,
                    metadata TEXT,
                    tags TEXT
                )
                """)
            self.conn.commit()

    @staticmethod
    def _dt(v):
        return datetime.fromisoformat(v) if v else None

    @staticmethod
    def _record(row):
        if row is None:
            return None
        return MemoryRecord(
            id=row["id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            conversation_id=row["conversation_id"],
            memory_type=row["memory_type"],
            category=row["category"] or "",
            key=row["memory_key"],
            value=row["memory_value"],
            summary=row["summary"] or "",
            importance=row["importance"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=SQLiteMemoryStore._dt(row["created_at"]) or datetime.now(UTC),
            updated_at=SQLiteMemoryStore._dt(row["updated_at"]) or datetime.now(UTC),
            last_accessed=SQLiteMemoryStore._dt(row["last_accessed"]),
            access_count=row["access_count"] or 0,
            expires_at=SQLiteMemoryStore._dt(row["expires_at"]),
            embedding_id=row["embedding_id"],
            parent_memory_id=row["parent_memory_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            tags=json.loads(row["tags"] or "[]"),
        )

    def save(self, memory: MemoryRecord) -> MemoryRecord:
        self.logger.info(
            "INSERT executed for memory_id=%s key=%s", memory.id, memory.key
        )
        with self._lock:
            self.conn.execute(
                """INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    memory.id,
                    memory.user_id,
                    memory.project_id,
                    memory.conversation_id,
                    memory.memory_type,
                    memory.category,
                    memory.key,
                    memory.value,
                    memory.summary,
                    memory.importance,
                    memory.confidence,
                    memory.source,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.access_count,
                    memory.expires_at.isoformat() if memory.expires_at else None,
                    memory.embedding_id,
                    memory.parent_memory_id,
                    json.dumps(memory.metadata),
                    json.dumps(memory.tags),
                ),
            )
            self.conn.commit()
        self.logger.info("INSERT commit completed for memory_id=%s", memory.id)
        return memory

    def update(self, memory: MemoryRecord) -> MemoryRecord:
        self.logger.info(
            "UPDATE executed for memory_id=%s key=%s", memory.id, memory.key
        )
        with self._lock:
            self.conn.execute(
                """UPDATE memories SET
                category=?,memory_value=?,summary=?,importance=?,confidence=?,updated_at=?,
                last_accessed=?,access_count=?,metadata=?,tags=?
                WHERE id=?""",
                (
                    memory.category,
                    memory.value,
                    memory.summary,
                    memory.importance,
                    memory.confidence,
                    memory.updated_at.isoformat(),
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.access_count,
                    json.dumps(memory.metadata),
                    json.dumps(memory.tags),
                    memory.id,
                ),
            )
            self.conn.commit()
        self.logger.info("UPDATE commit completed for memory_id=%s", memory.id)
        return memory

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            self.conn.commit()
        return cur.rowcount > 0

    def get(self, memory_id: str):
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
        return self._record(row)

    def get_all(self):
        with self._lock:
            rows = list(self.conn.execute("SELECT * FROM memories"))
        return [self._record(r) for r in rows]

    def find_by_key(self, user_id: str, key: str):
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM memories WHERE user_id=? AND memory_key=?",
                (user_id, key),
            ).fetchone()
        return self._record(row)

    def find_by_type(self, user_id: str, memory_type: str):
        with self._lock:
            rows = list(
                self.conn.execute(
                    "SELECT * FROM memories WHERE user_id=? AND memory_type=?",
                    (user_id, memory_type),
                )
            )
        return [self._record(r) for r in rows]

    def search(self, user_id: str, query: str):
        q = f"%{query}%"
        with self._lock:
            rows = list(
                self.conn.execute(
                    """SELECT * FROM memories
                   WHERE user_id=? AND
                   (memory_key LIKE ? OR memory_value LIKE ? OR summary LIKE ?)""",
                    (user_id, q, q, q),
                )
            )
        return [self._record(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
