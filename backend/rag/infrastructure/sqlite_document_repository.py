"""SQLite repository for document records."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from backend.rag.domain.interfaces import DocumentRepository
from backend.rag.domain.models import DocumentRecord


class SQLiteDocumentRepository(DocumentRepository):
    """Persist document metadata records in SQLite."""

    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    embedding_status TEXT NOT NULL,
                    index_status TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            self.connection.commit()

    def save(self, document: DocumentRecord) -> DocumentRecord:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO rag_documents (
                    id,
                    name,
                    original_filename,
                    stored_path,
                    file_type,
                    size_bytes,
                    sha256,
                    chunk_count,
                    embedding_status,
                    index_status,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.name,
                    document.original_filename,
                    document.stored_path,
                    document.file_type,
                    document.size_bytes,
                    document.sha256,
                    document.chunk_count,
                    document.embedding_status,
                    document.index_status,
                    json.dumps(document.metadata, sort_keys=True),
                    document.created_at.isoformat(),
                    document.updated_at.isoformat(),
                ),
            )
            self.connection.commit()
        return document

    def update(self, document: DocumentRecord) -> DocumentRecord:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE rag_documents
                SET
                    name = ?,
                    original_filename = ?,
                    stored_path = ?,
                    file_type = ?,
                    size_bytes = ?,
                    sha256 = ?,
                    chunk_count = ?,
                    embedding_status = ?,
                    index_status = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    document.name,
                    document.original_filename,
                    document.stored_path,
                    document.file_type,
                    document.size_bytes,
                    document.sha256,
                    document.chunk_count,
                    document.embedding_status,
                    document.index_status,
                    json.dumps(document.metadata, sort_keys=True),
                    document.updated_at.isoformat(),
                    document.id,
                ),
            )
            self.connection.commit()
        return document

    def list_all(self) -> list[DocumentRecord]:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM rag_documents ORDER BY created_at DESC")
            rows = cursor.fetchall()
        return [self._row_to_document(row) for row in rows]

    def get(self, document_id: str) -> DocumentRecord | None:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM rag_documents WHERE id = ?", (document_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_document(row)

    def delete(self, document_id: str) -> bool:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM rag_documents WHERE id = ?", (document_id,))
            self.connection.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM rag_documents")
            self.connection.commit()
            return int(cursor.rowcount)

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def _row_to_document(self, row: sqlite3.Row) -> DocumentRecord:
        from datetime import datetime

        return DocumentRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            original_filename=str(row["original_filename"]),
            stored_path=str(row["stored_path"]),
            file_type=str(row["file_type"]),
            size_bytes=int(row["size_bytes"]),
            sha256=str(row["sha256"]),
            chunk_count=int(row["chunk_count"]),
            embedding_status=str(row["embedding_status"]),
            index_status=str(row["index_status"]),
            metadata=json.loads(str(row["metadata"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
