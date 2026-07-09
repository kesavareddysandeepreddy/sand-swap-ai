from __future__ import annotations

from pathlib import Path

from backend.rag.domain.models import DocumentChunk
from backend.rag.embeddings.providers import DeterministicMockEmbeddingProvider
from backend.rag.retrievers.semantic_retriever import SemanticRetriever
from backend.rag.vectorstores.sqlite_vector_store import SQLiteVectorStore


def _chunk(chunk_id: str, text: str, document_id: str = "doc-1") -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        document_name="doc.txt",
        text=text,
        file_type="txt",
        metadata={
            "document_id": document_id,
            "file_type": "txt",
            "category": "document",
        },
    )


def test_sqlite_vector_store_retrieves_top_k(tmp_path: Path) -> None:
    store = SQLiteVectorStore(db_path=str(tmp_path / "rag.db"))
    embedder = DeterministicMockEmbeddingProvider()

    chunks = [
        _chunk("c-1", "deployment pipeline for kubernetes"),
        _chunk("c-2", "user profile favorite color is blue"),
        _chunk("c-3", "terraform module for network setup"),
    ]
    vectors = embedder.embed_batch([chunk.text for chunk in chunks])
    store.upsert_chunks(chunks, vectors)

    query = embedder.embed_text("how is kubernetes deployment configured")
    result = store.retrieve(query_vector=query, top_k=2)

    assert len(result) == 2
    assert {chunk.chunk_id for chunk in result}.issubset({"c-1", "c-2", "c-3"})
    assert result[0].score >= result[1].score


def test_semantic_retriever_supports_metadata_filter(tmp_path: Path) -> None:
    store = SQLiteVectorStore(db_path=str(tmp_path / "rag-filter.db"))
    embedder = DeterministicMockEmbeddingProvider()
    retriever = SemanticRetriever(embedding_provider=embedder, vector_store=store)

    chunks = [
        _chunk("f-1", "api route for payments", document_id="doc-api"),
        _chunk("f-2", "loop diagram for compressor control", document_id="doc-eng"),
    ]
    store.upsert_chunks(chunks, embedder.embed_batch([chunk.text for chunk in chunks]))

    filtered = retriever.retrieve(
        query="control loop",
        top_k=5,
        metadata_filter={"document_id": "doc-eng"},
    )

    assert len(filtered) == 1
    assert filtered[0].document_id == "doc-eng"
