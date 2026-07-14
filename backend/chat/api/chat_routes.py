"""Chat API routes."""

from __future__ import annotations

from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUserDependency,
    OwnershipContextDependency,
)
from backend.api.dependencies import get_chat_service as resolve_chat_service
from backend.chat.application.chat_service import ChatService
from backend.core.logging.logger import LoggerFactory
from backend.services import resolve_owner_id, resolve_project_id, resolve_workspace_id

router = APIRouter(prefix="/chat", tags=["chat"])
logger = LoggerFactory.get_logger("ChatRoutes")


class ChatRequest(BaseModel):
    """Request payload for sending a chat message."""

    user_id: str | None = Field(default=None, min_length=1)
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    model: str | None = None


class ChatResponse(BaseModel):
    """Response payload for chat interactions."""

    conversation_id: str
    response: str
    memories_saved: int = 0


class ChatModelsResponse(BaseModel):
    """Response payload listing available chat models."""

    models: list[str]


class ChatMessagePayload(BaseModel):
    """Serialized chat message for conversation list responses."""

    id: str
    role: str
    content: str
    created_at: str


class ChatConversationPayload(BaseModel):
    """Serialized conversation state returned by list endpoint."""

    id: str
    title: str
    updated_at: str
    messages: list[ChatMessagePayload]


class ChatConversationListResponse(BaseModel):
    """Response payload for persisted chat conversations."""

    items: list[ChatConversationPayload]


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ChatResponse:
    """Send a user message to the chat service."""
    fallback_user_id = request.user_id
    if fallback_user_id is None and not current_user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anonymous session id is required",
        )

    effective_user_id = resolve_owner_id(
        current_user,
        fallback_user_id=fallback_user_id,
    )
    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    try:
        result = await chat_service.send_message(
            user_id=effective_user_id,
            message=request.message,
            conversation_id=request.conversation_id,
            model=request.model,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except KeyError as exc:
        logger.warning("Chat service could not resolve the conversation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc
    except ValueError as exc:
        logger.warning("Chat request validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (requests.RequestException, RuntimeError) as exc:
        logger.exception("Chat service request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat service unavailable",
        ) from exc

    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
        memories_saved=0,
    )


@router.get("/models", response_model=ChatModelsResponse)
def list_models(
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
) -> ChatModelsResponse:
    """Return available Ollama model names for chat."""
    try:
        models = chat_service.ollama_client.list_models()
    except requests.RequestException as exc:
        logger.warning("Unable to list models from Ollama: %s", exc)
        models = []

    if not models and getattr(chat_service.ollama_client, "model", None):
        models = [chat_service.ollama_client.model]

    deduped: list[str] = []
    seen = set()
    for model in models:
        normalized = model.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return ChatModelsResponse(models=deduped)


@router.get("/conversations", response_model=ChatConversationListResponse)
async def list_conversations(
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ChatConversationListResponse:
    """List persisted conversations for the active user/workspace/project scope."""
    if not current_user.is_authenticated or current_user.user_id is None:
        return ChatConversationListResponse(items=[])

    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    items = await chat_service.list_conversations(
        user_id=current_user.user_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return ChatConversationListResponse(items=items)
