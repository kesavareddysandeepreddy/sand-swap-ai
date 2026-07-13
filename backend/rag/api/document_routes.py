"""Document ingestion and retrieval API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUserDependency,
    OwnershipContextDependency,
    get_document_ingestion_service,
    get_document_retrieval_service,
)
from backend.core.logging.logger import LoggerFactory
from backend.rag.application.document_service import (
    DocumentIngestionService,
    DocumentRetrievalService,
)
from backend.rag.domain.models import DocumentRecord, RetrievedChunk
from backend.services import resolve_owner_id, resolve_workspace_id

router = APIRouter(prefix="/documents", tags=["documents"])
logger = LoggerFactory.get_logger("DocumentRoutes")


class DocumentResponse(BaseModel):
    """Serialized document metadata response."""

    id: str
    name: str
    original_filename: str
    stored_path: str
    file_type: str
    size_bytes: int
    chunk_count: int
    embedding_status: str
    index_status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DeleteManyResponse(BaseModel):
    """Result payload for bulk deletion."""

    deleted: int


class RetrievalRequest(BaseModel):
    """Request payload for retrieval inspector."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None
    file_type: str | None = None
    category: str | None = None


class RetrievedChunkResponse(BaseModel):
    """Retrieved chunk payload for UI and prompt citations."""

    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: dict[str, Any]


class RetrievalResponse(BaseModel):
    """Retrieval inspector response."""

    chunks: list[RetrievedChunkResponse]
    citations: list[str]


def _serialize_document(document: DocumentRecord) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        name=document.name,
        original_filename=document.original_filename,
        stored_path=document.stored_path,
        file_type=document.file_type,
        size_bytes=document.size_bytes,
        chunk_count=document.chunk_count,
        embedding_status=document.embedding_status,
        index_status=document.index_status,
        metadata=document.metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _serialize_chunk(chunk: RetrievedChunk) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_name=chunk.document_name,
        text=chunk.text,
        score=chunk.score,
        metadata=chunk.metadata,
    )


@router.post(
    "/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    file: UploadFile = File(...),
    project: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    chunk_size: int | None = Form(default=None, ge=1, le=200),
    overlap: int | None = Form(default=None, ge=0, le=100),
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> DocumentResponse:
    """Upload, parse, chunk, and index a document."""
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    try:
        document = await service.upload_document(
            file,
            owner_id=owner_id,
            project=project or workspace_id,
            tags=[tag for tag in tag_list if tag],
            chunk_size=chunk_size,
            overlap=overlap,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return _serialize_document(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> list[DocumentResponse]:
    """List all uploaded documents."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    return [
        _serialize_document(document)
        for document in service.list_documents(
            owner_id=owner_id,
            project_id=workspace_id,
        )
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> DocumentResponse:
    """Fetch one uploaded document metadata record."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    document = service.get_document(
        document_id,
        owner_id=owner_id,
        project_id=workspace_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return _serialize_document(document)


@router.get("/{document_id}/chunks", response_model=list[RetrievedChunkResponse])
def get_document_chunks(
    document_id: str,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> list[RetrievedChunkResponse]:
    """List indexed chunks for a document."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    document = service.get_document(
        document_id,
        owner_id=owner_id,
        project_id=workspace_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return [
        _serialize_chunk(chunk)
        for chunk in service.list_document_chunks(
            document_id,
            owner_id=owner_id,
            project_id=workspace_id,
        )
    ]


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve_chunks(
    payload: RetrievalRequest,
    service: DocumentRetrievalService = Depends(get_document_retrieval_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> RetrievalResponse:
    """Retrieve top matching chunks for inspector and context building."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    logger.info(
        "retrieve_chunks() input query=%r top_k=%s owner_filter=%s document_filter=%s file_type_filter=%s category_filter=%s project_filter=%s conversation_filter=%s",
        payload.query,
        payload.top_k,
        owner_id,
        payload.document_id,
        payload.file_type,
        payload.category,
        workspace_id,
        None,
    )
    chunks = service.retrieve(
        query=payload.query,
        top_k=payload.top_k,
        owner_id=owner_id,
        project_id=workspace_id,
        document_id=payload.document_id,
        file_type=payload.file_type,
        category=payload.category,
    )
    logger.info(
        "retrieve_chunks() output chunk_count=%s similarity_scores=%s owner_filter=%s",
        len(chunks),
        [round(chunk.score, 6) for chunk in chunks[:5]],
        owner_id,
    )
    return RetrievalResponse(
        chunks=[_serialize_chunk(chunk) for chunk in chunks],
        citations=service.format_citations(chunks),
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> None:
    """Delete one document and all its indexed chunks."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    deleted = service.delete_document(
        document_id,
        owner_id=owner_id,
        project_id=workspace_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )


@router.delete("", response_model=DeleteManyResponse)
def delete_all_documents(
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
    current_user: CurrentUserDependency = None,
    ownership_context: OwnershipContextDependency = None,
) -> DeleteManyResponse:
    """Delete all uploaded documents and indexed chunks."""
    owner_id = resolve_owner_id(current_user)
    workspace_id = resolve_workspace_id(ownership_context)
    deleted = service.delete_all_documents(owner_id=owner_id, project_id=workspace_id)
    return DeleteManyResponse(deleted=deleted)
