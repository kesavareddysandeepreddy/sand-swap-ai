"""Knowledge source management API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    KnowledgeSourceServiceDependency,
    OwnershipContextDependency,
    RequiredCurrentUserDependency,
    get_document_ingestion_service,
)
from backend.knowledge_sources.models import KnowledgeSource
from backend.knowledge_sources.source_types import SourceType
from backend.rag.application.document_service import DocumentIngestionService

router = APIRouter(prefix="/api/knowledge-sources", tags=["knowledge-sources"])


class KnowledgeSourceCreateRequest(BaseModel):
    """Request payload to create a new knowledge source."""

    project_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    source_type: SourceType
    connection_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceResponse(BaseModel):
    """Serialized knowledge source payload."""

    id: str
    project_id: str
    name: str
    source_type: SourceType
    connection_config: dict[str, Any]
    enabled: bool
    status: str
    file_count: int
    chunk_count: int
    embedding_count: int
    last_sync: datetime | None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


class DeleteKnowledgeSourceResponse(BaseModel):
    """Delete operation response."""

    deleted: bool


class KnowledgeSourcesHealthResponse(BaseModel):
    """Health payload for knowledge source runtime."""

    status: str
    connectors_total: int
    connectors: dict[str, str]


class ConnectorConfigureRequest(BaseModel):
    """Request payload for connector authentication/configuration."""

    connection_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorOperationResponse(BaseModel):
    """Generic connector operation response payload."""

    source_id: str
    status: str
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorDiscoveryResponse(BaseModel):
    """Connector discovery payload for repository/site/library/folder browsing."""

    source_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)


def _serialize_source(source: KnowledgeSource) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=source.id,
        project_id=source.project_id,
        name=source.name,
        source_type=source.source_type,
        connection_config=source.connection_config,
        enabled=source.enabled,
        status=source.status,
        file_count=source.file_count,
        chunk_count=source.chunk_count,
        embedding_count=source.embedding_count,
        last_sync=source.last_sync,
        created_at=source.created_at,
        updated_at=source.updated_at,
        metadata=source.metadata,
    )


@router.get("", response_model=list[KnowledgeSourceResponse])
def list_knowledge_sources(
    service: KnowledgeSourceServiceDependency,
    project_id: str = Query(..., min_length=1),
) -> list[KnowledgeSourceResponse]:
    """List knowledge sources for one project."""
    return [_serialize_source(source) for source in service.list_sources(project_id)]


@router.post(
    "",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_source(
    payload: KnowledgeSourceCreateRequest,
    service: KnowledgeSourceServiceDependency,
) -> KnowledgeSourceResponse:
    """Create a new project knowledge source."""
    source = service.create_source(
        project_id=payload.project_id,
        name=payload.name,
        source_type=payload.source_type,
        connection_config=dict(payload.connection_config),
        metadata=dict(payload.metadata),
    )
    return _serialize_source(source)


@router.delete("/{source_id}", response_model=DeleteKnowledgeSourceResponse)
def delete_knowledge_source(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
) -> DeleteKnowledgeSourceResponse:
    """Delete one knowledge source by id."""
    deleted = service.remove_source(source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )
    return DeleteKnowledgeSourceResponse(deleted=True)


@router.put("/{source_id}/enable", response_model=KnowledgeSourceResponse)
def enable_knowledge_source(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
) -> KnowledgeSourceResponse:
    """Enable one knowledge source."""
    try:
        source = service.enable_source(source_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return _serialize_source(source)


@router.put("/{source_id}/disable", response_model=KnowledgeSourceResponse)
def disable_knowledge_source(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
) -> KnowledgeSourceResponse:
    """Disable one knowledge source."""
    try:
        source = service.disable_source(source_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return _serialize_source(source)


@router.get("/health", response_model=KnowledgeSourcesHealthResponse)
def knowledge_sources_health(
    service: KnowledgeSourceServiceDependency,
) -> KnowledgeSourcesHealthResponse:
    """Return health metadata for the knowledge source platform."""
    health = service.health()
    return KnowledgeSourcesHealthResponse(
        status=str(health.get("status", "unknown")),
        connectors_total=int(health.get("connectors_total", 0)),
        connectors={
            str(key): str(value)
            for key, value in dict(health.get("connectors", {})).items()
        },
    )


@router.post(
    "/{source_id}/connector/connect", response_model=ConnectorOperationResponse
)
def connect_knowledge_source_connector(
    source_id: str,
    payload: ConnectorConfigureRequest,
    service: KnowledgeSourceServiceDependency,
    current_user: RequiredCurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ConnectorOperationResponse:
    """Authenticate and persist connector configuration for a source."""
    connection_config = dict(payload.connection_config)
    # Inject authenticated identity so ingestion metadata is correct
    if current_user.user_id:
        connection_config.setdefault("owner_id", current_user.user_id)
        connection_config.setdefault(
            "workspace_id", ownership_context.get("workspace_id", "default")
        )
        connection_config.setdefault(
            "project_id", ownership_context.get("project_id", "default")
        )
    try:
        updated = service.configure_connector(
            source_id=source_id,
            connection_config=connection_config,
            metadata=dict(payload.metadata),
            owner_id=current_user.user_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ConnectorOperationResponse(
        source_id=updated.id,
        status=updated.status,
        detail="Connector connected",
        metadata=dict(updated.metadata),
    )


@router.get(
    "/{source_id}/connector/discover", response_model=ConnectorDiscoveryResponse
)
def discover_knowledge_source_connector(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
) -> ConnectorDiscoveryResponse:
    """Discover available resources for a source connector."""
    try:
        items = service.discover_connector_resources(source_id=source_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return ConnectorDiscoveryResponse(source_id=source_id, items=items)


@router.post("/{source_id}/connector/sync", response_model=KnowledgeSourceResponse)
def sync_knowledge_source_connector(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
    current_user: RequiredCurrentUserDependency,
    ownership_context: OwnershipContextDependency,
    incremental: bool = Query(default=False),
) -> KnowledgeSourceResponse:
    """Run full or incremental connector synchronization for one source."""
    try:
        updated = service.sync_connector(
            source_id=source_id,
            incremental=incremental,
            owner_id=current_user.user_id,
            workspace_id=ownership_context.get("workspace_id"),
            project_id=ownership_context.get("project_id"),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return _serialize_source(updated)


@router.post("/{source_id}/connector/reindex", response_model=KnowledgeSourceResponse)
def reindex_knowledge_source_connector(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
    current_user: RequiredCurrentUserDependency,
    ownership_context: OwnershipContextDependency,
    ingestion_service: Annotated[
        DocumentIngestionService, Depends(get_document_ingestion_service)
    ],
) -> KnowledgeSourceResponse:
    """Purge previously indexed documents for this source and reindex with correct auth metadata."""
    try:
        source = service._repository.get(source_id)
        if source is None:
            raise KeyError(source_id)

        # Remove all chunks indexed from this source (identified by source_id in metadata)
        all_chunks = ingestion_service.vector_store.list_chunks()
        source_doc_ids = {
            chunk.document_id
            for chunk in all_chunks
            if chunk.metadata.get("source_id") == source_id
        }
        for doc_id in source_doc_ids:
            ingestion_service.vector_store.delete_document(doc_id)
            ingestion_service.repository.delete(doc_id)

        updated = service.sync_connector(
            source_id=source_id,
            owner_id=current_user.user_id,
            workspace_id=ownership_context.get("workspace_id"),
            project_id=ownership_context.get("project_id"),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return _serialize_source(updated)


@router.get("/{source_id}/connector/health", response_model=ConnectorOperationResponse)
def connector_health(
    source_id: str,
    service: KnowledgeSourceServiceDependency,
) -> ConnectorOperationResponse:
    """Return connector health details for one source."""
    try:
        payload = service.connector_health(source_id=source_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from exc
    return ConnectorOperationResponse(
        source_id=source_id,
        status=str(payload.get("status", "unknown")),
        detail=str(payload.get("message", "")),
        metadata={
            "connected": bool(payload.get("connected", False)),
            "details": dict(payload.get("details", {})),
        },
    )
