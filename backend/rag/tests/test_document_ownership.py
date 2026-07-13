from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from backend.rag.application.document_service import (
    DocumentIngestionService,
    DocumentRetrievalService,
)
from backend.rag.chunkers.factory import ChunkerFactory
from backend.rag.embeddings.providers import EmbeddingProviderFactory
from backend.rag.infrastructure.sqlite_document_repository import (
    SQLiteDocumentRepository,
)
from backend.rag.parsers.factory import ParserFactory
from backend.rag.retrievers.semantic_retriever import SemanticRetriever
from backend.rag.vectorstores.sqlite_vector_store import SQLiteVectorStore
from backend.services import ANONYMOUS_USER_ID


@pytest.fixture
def document_services(
    tmp_path: Path,
) -> tuple[DocumentIngestionService, DocumentRetrievalService]:
    repository = SQLiteDocumentRepository(str(tmp_path / "documents.db"))
    vector_store = SQLiteVectorStore(str(tmp_path / "vectors.db"))
    embedding_provider = EmbeddingProviderFactory().create(provider="mock", config={})
    ingestion = DocumentIngestionService(
        repository=repository,
        parser_factory=ParserFactory(),
        chunker_factory=ChunkerFactory(semantic=True),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        storage_dir=str(tmp_path / "uploads"),
    )
    retrieval = DocumentRetrievalService(
        retriever=SemanticRetriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        )
    )
    return ingestion, retrieval


@pytest.mark.asyncio
async def test_documents_are_scoped_by_owner(
    document_services: tuple[DocumentIngestionService, DocumentRetrievalService],
) -> None:
    ingestion, retrieval = document_services

    alice_document = await ingestion.upload_document(
        UploadFile(
            file=BytesIO(b"Alice deployment runbook"),
            filename="alice.txt",
        ),
        owner_id="alice",
    )
    anonymous_document = await ingestion.upload_document(
        UploadFile(
            file=BytesIO(b"Anonymous deployment guide"),
            filename="anonymous.txt",
        ),
    )

    assert ingestion.list_documents(owner_id="alice") == [alice_document]
    assert ingestion.list_documents(owner_id=ANONYMOUS_USER_ID) == [anonymous_document]
    assert ingestion.get_document(alice_document.id, owner_id="bob") is None

    alice_chunks = retrieval.retrieve(
        query="deployment",
        owner_id="alice",
        top_k=5,
    )
    anonymous_chunks = retrieval.retrieve(
        query="deployment",
        owner_id=ANONYMOUS_USER_ID,
        top_k=5,
    )

    assert {chunk.document_id for chunk in alice_chunks} == {alice_document.id}
    assert {chunk.document_id for chunk in anonymous_chunks} == {anonymous_document.id}


@pytest.mark.asyncio
async def test_delete_all_documents_only_removes_requested_owner_records(
    document_services: tuple[DocumentIngestionService, DocumentRetrievalService],
) -> None:
    ingestion, _ = document_services

    await ingestion.upload_document(
        UploadFile(file=BytesIO(b"alpha"), filename="alpha.txt"),
        owner_id="alice",
    )
    anonymous_document = await ingestion.upload_document(
        UploadFile(file=BytesIO(b"beta"), filename="beta.txt"),
    )

    deleted = ingestion.delete_all_documents(owner_id="alice")

    assert deleted == 1
    remaining = ingestion.list_documents(owner_id=ANONYMOUS_USER_ID)
    assert [document.id for document in remaining] == [anonymous_document.id]


@pytest.mark.asyncio
async def test_owner_scoped_retrieval_falls_back_to_anonymous_legacy_documents(
    document_services: tuple[DocumentIngestionService, DocumentRetrievalService],
) -> None:
    ingestion, retrieval = document_services

    anonymous_document = await ingestion.upload_document(
        UploadFile(
            file=BytesIO(b"Anonymous deployment guide"),
            filename="anonymous.txt",
        ),
    )

    chunks = retrieval.retrieve(
        query="deployment",
        owner_id="user-1",
        top_k=5,
    )

    assert {chunk.document_id for chunk in chunks} == {anonymous_document.id}
