"""SQLite-backed vector store for RAG chunks."""

from __future__ import annotations

import json
import sqlite3
import threading
from math import sqrt
from pathlib import Path
from typing import Any

from backend.core.logging.logger import LoggerFactory
from backend.rag.domain.interfaces import VectorStore
from backend.rag.domain.models import DocumentChunk, RetrievedChunk
from backend.services import normalize_user_id


class SQLiteVectorStore(VectorStore):
    """Persist chunk vectors and support cosine retrieval."""

    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.logger = LoggerFactory.get_logger("SQLiteVectorStore")
        self._initialize()

    def _initialize(self) -> None:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    vector TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON rag_chunks (document_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_chunks_type ON rag_chunks (file_type)"
            )
            self.connection.commit()

    def upsert_chunks(
        self, chunks: list[DocumentChunk], vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")

        with self.lock:
            cursor = self.connection.cursor()
            for chunk, vector in zip(chunks, vectors, strict=True):
                cursor.execute(
                    """
                    INSERT INTO rag_chunks (
                        chunk_id,
                        document_id,
                        document_name,
                        file_type,
                        content,
                        vector,
                        metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        document_id=excluded.document_id,
                        document_name=excluded.document_name,
                        file_type=excluded.file_type,
                        content=excluded.content,
                        vector=excluded.vector,
                        metadata=excluded.metadata
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.document_name,
                        chunk.file_type,
                        chunk.text,
                        json.dumps(vector),
                        json.dumps(chunk.metadata, sort_keys=True),
                    ),
                )
                self.logger.debug(
                    "VECTOR_STORED chunk_id=%s document_id=%s owner_id=%s workspace_id=%s project_id=%s",
                    chunk.id,
                    chunk.document_id,
                    chunk.metadata.get("owner_id"),
                    chunk.metadata.get("workspace_id"),
                    chunk.metadata.get("project"),
                )
            self.connection.commit()

    def delete_document(self, document_id: str) -> int:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(
                "DELETE FROM rag_chunks WHERE document_id = ?", (document_id,)
            )
            self.connection.commit()
            return int(cursor.rowcount)

    def clear(self) -> int:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM rag_chunks")
            self.connection.commit()
            return int(cursor.rowcount)

    def list_chunks(self, document_id: str | None = None) -> list[RetrievedChunk]:
        with self.lock:
            cursor = self.connection.cursor()
            if document_id:
                cursor.execute(
                    "SELECT * FROM rag_chunks WHERE document_id = ? ORDER BY created_at ASC",
                    (document_id,),
                )
            else:
                cursor.execute("SELECT * FROM rag_chunks ORDER BY created_at ASC")
            rows = cursor.fetchall()

        return [
            RetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                document_name=str(row["document_name"]),
                text=str(row["content"]),
                score=0.0,
                metadata=json.loads(str(row["metadata"])),
            )
            for row in rows
        ]

    def retrieve(
        self,
        query_vector: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM rag_chunks")
            rows = cursor.fetchall()

        metadata_rows = [json.loads(str(row["metadata"])) for row in rows]
        filter_trace = self._build_filter_trace(
            metadata_rows=metadata_rows,
            metadata_filter=metadata_filter,
        )

        results: list[RetrievedChunk] = []
        filtered_counts: dict[str, int] = {}
        for row in rows:
            metadata = json.loads(str(row["metadata"]))
            filter_reason = self._filter_mismatch_reason(metadata, metadata_filter)
            if filter_reason is not None:
                filtered_counts[filter_reason] = (
                    filtered_counts.get(filter_reason, 0) + 1
                )
                continue

            vector = [float(value) for value in json.loads(str(row["vector"]))]
            score = self._cosine_similarity(query_vector, vector)
            chunk = RetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                document_name=str(row["document_name"]),
                text=str(row["content"]),
                score=score,
                metadata=metadata,
            )
            self.logger.debug(
                "RETRIEVAL_MATCH chunk_id=%s owner_id=%s workspace_id=%s project_id=%s score=%.6f",
                chunk.chunk_id,
                metadata.get("owner_id"),
                metadata.get("workspace_id"),
                metadata.get("project"),
                score,
            )
            results.append(chunk)

        results.sort(key=lambda chunk: chunk.score, reverse=True)
        selected = results[:top_k]
        self.logger.info(
            "retrieve() filter_trace total_chunks=%s after_owner_filter=%s after_workspace_filter=%s after_project_filter=%s zero_filter=%s owner_filter=%s workspace_filter=%s project_filter=%s",
            filter_trace["total_chunks"],
            filter_trace["after_owner_filter"],
            filter_trace["after_workspace_filter"],
            filter_trace["after_project_filter"],
            filter_trace["zero_filter"],
            filter_trace["owner_filter"],
            filter_trace["workspace_filter"],
            filter_trace["project_filter"],
        )
        self.logger.info(
            "retrieve() input query_vector_dims=%s total_chunks=%s metadata_filter=%s filtered_counts=%s output_chunk_count=%s similarity_scores=%s owner_filter=%s project_filter=%s conversation_filter=%s",
            len(query_vector),
            len(rows),
            metadata_filter,
            filtered_counts,
            len(selected),
            [round(chunk.score, 6) for chunk in selected[:5]],
            (metadata_filter or {}).get("owner_id") if metadata_filter else None,
            (metadata_filter or {}).get("project") if metadata_filter else None,
            (metadata_filter or {}).get("conversation_id") if metadata_filter else None,
        )
        return selected

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def _matches_filter(
        self, metadata: dict[str, Any], filters: dict[str, Any]
    ) -> bool:
        return self._filter_mismatch_reason(metadata, filters) is None

    def _filter_mismatch_reason(
        self,
        metadata: dict[str, Any],
        filters: dict[str, Any] | None,
    ) -> str | None:
        if not filters:
            return None

        for key, expected in filters.items():
            if key in {"document_id", "file_type", "category", "owner_id"}:
                value = metadata.get(key)
                if key == "owner_id":
                    value = normalize_user_id(value if isinstance(value, str) else None)
                    if isinstance(expected, list):
                        normalized_expected = [
                            normalize_user_id(str(item)) for item in expected
                        ]
                        if value not in normalized_expected:
                            return f"owner_id:{value}!={normalized_expected}"
                        continue
                    if value != normalize_user_id(str(expected)):
                        return f"owner_id:{value}!={normalize_user_id(str(expected))}"
                    continue
                if isinstance(expected, list):
                    if value not in expected:
                        return f"{key}:{value}!={expected}"
                elif value != expected:
                    return f"{key}:{value}!={expected}"
                continue

            if metadata.get(key) != expected:
                return f"{key}:{metadata.get(key)}!={expected}"

        return None

    def _build_filter_trace(
        self,
        *,
        metadata_rows: list[dict[str, Any]],
        metadata_filter: dict[str, Any] | None,
    ) -> dict[str, Any]:
        trace = {
            "total_chunks": len(metadata_rows),
            "after_owner_filter": len(metadata_rows),
            "after_workspace_filter": len(metadata_rows),
            "after_project_filter": len(metadata_rows),
            "zero_filter": None,
            "owner_filter": None,
            "workspace_filter": None,
            "project_filter": None,
        }
        if not metadata_filter:
            return trace

        remaining = list(metadata_rows)

        owner_expected = metadata_filter.get("owner_id")
        trace["owner_filter"] = owner_expected
        if owner_expected is not None:
            remaining = [
                metadata
                for metadata in remaining
                if self._filter_mismatch_reason(metadata, {"owner_id": owner_expected})
                is None
            ]
            trace["after_owner_filter"] = len(remaining)
            if not remaining:
                trace["zero_filter"] = "owner_id"
                return trace

        workspace_expected = metadata_filter.get("workspace_id")
        trace["workspace_filter"] = workspace_expected
        if workspace_expected is not None:
            remaining = [
                metadata
                for metadata in remaining
                if self._filter_mismatch_reason(
                    metadata,
                    {"workspace_id": workspace_expected},
                )
                is None
            ]
            trace["after_workspace_filter"] = len(remaining)
            if not remaining:
                trace["zero_filter"] = "workspace_id"
                return trace

        project_expected = metadata_filter.get("project")
        trace["project_filter"] = project_expected
        if project_expected is not None:
            remaining = [
                metadata
                for metadata in remaining
                if self._filter_mismatch_reason(metadata, {"project": project_expected})
                is None
            ]
            trace["after_project_filter"] = len(remaining)
            if not remaining:
                trace["zero_filter"] = "project"

        return trace

    def _cosine_similarity(self, lhs: list[float], rhs: list[float]) -> float:
        if not lhs or not rhs or len(lhs) != len(rhs):
            return 0.0
        numerator = sum(left * right for left, right in zip(lhs, rhs, strict=True))
        lhs_norm = sqrt(sum(value * value for value in lhs))
        rhs_norm = sqrt(sum(value * value for value in rhs))
        if lhs_norm == 0 or rhs_norm == 0:
            return 0.0
        return numerator / (lhs_norm * rhs_norm)
