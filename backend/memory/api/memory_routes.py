"""Memory management API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_memory_manager
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.models.memory_record import MemoryRecord

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryItem(BaseModel):
    """Serialized memory representation."""

    id: str
    user_id: str
    memory_type: str
    category: str
    key: str
    value: str
    summary: str
    importance: float
    confidence: float
    source: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any]
    tags: list[str]


class MemoryListResponse(BaseModel):
    """Paginated memory collection response."""

    items: list[MemoryItem]
    total: int
    page: int
    page_size: int


class MemoryUpdateRequest(BaseModel):
    """Fields that can be updated for a memory."""

    category: str | None = Field(default=None)
    key: str | None = Field(default=None)
    value: str | None = Field(default=None)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)


class DeleteAllResponse(BaseModel):
    """Delete-all operation result."""

    deleted: int


def _serialize_memory(memory: MemoryRecord) -> MemoryItem:
    return MemoryItem(
        id=memory.id,
        user_id=memory.user_id,
        memory_type=memory.memory_type,
        category=memory.category,
        key=memory.key,
        value=memory.value,
        summary=memory.summary,
        importance=memory.importance,
        confidence=memory.confidence,
        source=memory.source,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
        metadata=memory.metadata,
        tags=memory.tags,
    )


@router.get("", response_model=MemoryListResponse)
def list_memories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    min_importance: float | None = Query(default=None, ge=0.0, le=1.0),
    manager: MemoryManager = Depends(get_memory_manager),
) -> MemoryListResponse:
    """List memories with pagination and filters."""
    memories = manager.recall_all()

    if search:
        needle = search.lower().strip()
        memories = [
            memory
            for memory in memories
            if needle in memory.key.lower()
            or needle in memory.value.lower()
            or needle in memory.summary.lower()
        ]

    if category:
        normalized = category.lower().strip()
        memories = [
            memory for memory in memories if memory.category.lower() == normalized
        ]

    if min_importance is not None:
        memories = [
            memory for memory in memories if memory.importance >= min_importance
        ]

    ordered = sorted(memories, key=lambda memory: memory.created_at, reverse=True)
    total = len(ordered)

    start = (page - 1) * page_size
    end = start + page_size
    paged = ordered[start:end]

    return MemoryListResponse(
        items=[_serialize_memory(memory) for memory in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{memory_id}", response_model=MemoryItem)
def get_memory(
    memory_id: str,
    manager: MemoryManager = Depends(get_memory_manager),
) -> MemoryItem:
    """Get one memory by id."""
    memory = manager.store.get(memory_id)
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )
    return _serialize_memory(memory)


@router.patch("/{memory_id}", response_model=MemoryItem)
def update_memory(
    memory_id: str,
    payload: MemoryUpdateRequest,
    manager: MemoryManager = Depends(get_memory_manager),
) -> MemoryItem:
    """Update editable memory fields."""
    memory = manager.store.get(memory_id)
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    if payload.category is not None:
        memory.category = payload.category
    if payload.key is not None:
        memory.key = payload.key
    if payload.value is not None:
        memory.value = payload.value
    if payload.importance is not None:
        memory.importance = payload.importance

    memory.updated_at = datetime.now(UTC)
    updated = manager.store.update(memory)
    return _serialize_memory(updated)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    manager: MemoryManager = Depends(get_memory_manager),
) -> None:
    """Delete one memory by id."""
    deleted = manager.forget(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )


@router.delete("", response_model=DeleteAllResponse)
def delete_all_memories(
    manager: MemoryManager = Depends(get_memory_manager),
) -> DeleteAllResponse:
    """Delete all memories from the store."""
    all_memories = manager.recall_all()
    deleted = 0
    for memory in all_memories:
        if manager.forget(memory.id):
            deleted += 1

    return DeleteAllResponse(deleted=deleted)
