"""Chat API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
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


def _anonymous_owner_from_conversation_id(conversation_id: str) -> str | None:
    """Resolve anonymous owner id from a scoped conversation id.

    Expected scoped shape: anon-<session-id>:<conversation-uuid>
    """
    if ":" not in conversation_id:
        return None
    candidate_owner, _ = conversation_id.split(":", maxsplit=1)
    normalized = candidate_owner.strip()
    if not normalized.startswith("anon-"):
        return None
    return normalized


def _request_client_ip(request: Request) -> str:
    """Return best-effort client IP address for diagnostics."""
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client is not None else "unknown"


def _request_user_agent(request: Request) -> str:
    """Return best-effort user agent string for diagnostics."""
    return request.headers.get("user-agent", "unknown")


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


class ChatConversationDeleteResponse(BaseModel):
    """Response payload for conversation deletion."""

    conversation_id: str
    deleted: bool
    database_deleted: bool
    cache_deleted: bool
    memory_deleted: bool


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
    logger.info(
        "CHAT_API_REQUEST query=%r owner_id=%s workspace_id=%s project_id=%s",
        request.message,
        effective_user_id,
        workspace_id,
        project_id,
    )
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
    request: Request,
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ChatConversationListResponse:
    """List persisted conversations for the active user/workspace/project scope."""
    timestamp = datetime.now(timezone.utc).isoformat()
    client_ip = _request_client_ip(request)
    user_agent = _request_user_agent(request)

    if not current_user.is_authenticated or current_user.user_id is None:
        logger.info(
            "DIAG_CHAT_CONVERSATIONS_GET timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_returned=%s client_ip=%s user_agent=%r",
            timestamp,
            None,
            None,
            None,
            [],
            client_ip,
            user_agent,
        )
        return ChatConversationListResponse(items=[])

    workspace_id = resolve_workspace_id(ownership_context)
    project_id = resolve_project_id(ownership_context)
    items = await chat_service.list_conversations(
        user_id=current_user.user_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    conversation_ids_returned = [
        str(item.get("id", "")) for item in items if str(item.get("id", "")).strip()
    ]
    logger.info(
        "DIAG_CHAT_CONVERSATIONS_GET timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_returned=%s client_ip=%s user_agent=%r",
        timestamp,
        current_user.user_id,
        workspace_id,
        project_id,
        conversation_ids_returned,
        client_ip,
        user_agent,
    )
    return ChatConversationListResponse(items=items)


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ChatConversationDeleteResponse,
)
async def delete_conversation(
    request: Request,
    conversation_id: str,
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
    current_user: CurrentUserDependency,
    ownership_context: OwnershipContextDependency,
) -> ChatConversationDeleteResponse:
    """Delete a persisted conversation for the active user/workspace/project scope."""
    timestamp = datetime.now(timezone.utc).isoformat()
    client_ip = _request_client_ip(request)
    user_agent = _request_user_agent(request)

    effective_user_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None

    if current_user.is_authenticated and current_user.user_id is not None:
        effective_user_id = current_user.user_id
        workspace_id = resolve_workspace_id(ownership_context)
        project_id = resolve_project_id(ownership_context)
    else:
        anonymous_owner = _anonymous_owner_from_conversation_id(conversation_id)
        if anonymous_owner is None:
            logger.info(
                "DIAG_CHAT_CONVERSATIONS_DELETE timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_deleted=%s client_ip=%s user_agent=%r",
                timestamp,
                None,
                None,
                None,
                [],
                client_ip,
                user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        effective_user_id = anonymous_owner
        workspace_id = "default"
        project_id = "default"

    logger.info(
        "DELETE_TRACE_STEP2 route conversation_id=%s user_id=%s workspace_id=%s project_id=%s",
        conversation_id,
        effective_user_id,
        workspace_id,
        project_id,
    )

    try:
        result = await chat_service.delete_conversation(
            user_id=effective_user_id,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except ValueError as exc:
        logger.info(
            "DIAG_CHAT_CONVERSATIONS_DELETE timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_deleted=%s client_ip=%s user_agent=%r",
            timestamp,
            effective_user_id,
            workspace_id,
            project_id,
            [],
            client_ip,
            user_agent,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc

    if not result["deleted"]:
        logger.info(
            "DIAG_CHAT_CONVERSATIONS_DELETE timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_deleted=%s client_ip=%s user_agent=%r",
            timestamp,
            effective_user_id,
            workspace_id,
            project_id,
            [],
            client_ip,
            user_agent,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    logger.info(
        "DIAG_CHAT_CONVERSATIONS_DELETE timestamp=%s user_id=%s workspace_id=%s project_id=%s conversation_ids_deleted=%s client_ip=%s user_agent=%r",
        timestamp,
        effective_user_id,
        workspace_id,
        project_id,
        [conversation_id],
        client_ip,
        user_agent,
    )

    return ChatConversationDeleteResponse(
        conversation_id=conversation_id,
        deleted=result["deleted"],
        database_deleted=result["database_deleted"],
        cache_deleted=result["cache_deleted"],
        memory_deleted=result["memory_deleted"],
    )
