"""Chat API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.dependencies import get_chat_service as resolve_chat_service
from backend.chat.application.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


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
    result = await chat_service.send_message(
        user_id=request.user_id,
        message=request.message,
        conversation_id=request.conversation_id,
    )
    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
        memories_saved=0,
    )
