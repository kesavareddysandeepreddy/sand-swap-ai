"""Chat API routes."""

from __future__ import annotations

from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_chat_service as resolve_chat_service
from backend.chat.application.chat_service import ChatService
from backend.core.logging.logger import LoggerFactory

router = APIRouter(prefix="/chat", tags=["chat"])
logger = LoggerFactory.get_logger("ChatRoutes")


class ChatRequest(BaseModel):
    """Request payload for sending a chat message."""

    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Response payload for chat interactions."""

    conversation_id: str
    response: str
    memories_saved: int = 0


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(resolve_chat_service)],
) -> ChatResponse:
    """Send a user message to the chat service."""
    try:
        result = await chat_service.send_message(
            user_id=request.user_id,
            message=request.message,
            conversation_id=request.conversation_id,
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
