"""Conversation domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from backend.chat.domain.chat_message import ChatMessage


@dataclass(slots=True)
class Conversation:
    """Represents a single user conversation thread."""

    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    messages: list[ChatMessage] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> ChatMessage:
        """Append a new message and update timestamps."""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message

    def get_recent_messages(self, limit: int | None = None) -> list[ChatMessage]:
        """Return recent messages, ordered oldest to newest."""
        messages = list(self.messages)
        if limit is not None:
            return messages[-limit:]
        return messages

    def to_dict(self) -> dict[str, Any]:
        """Serialize the conversation to a dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [message.to_dict() for message in self.messages],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Conversation":
        """Create a conversation from serialized data."""
        messages = [
            ChatMessage(
                id=item.get("id", ""),
                role=item.get("role", "user"),
                content=item.get("content", ""),
                created_at=(
                    datetime.fromisoformat(item["created_at"])
                    if item.get("created_at")
                    else datetime.utcnow()
                ),
            )
            for item in payload.get("messages", [])
        ]
        return cls(
            id=payload.get("id", str(uuid4())),
            user_id=payload.get("user_id", ""),
            created_at=(
                datetime.fromisoformat(payload["created_at"])
                if payload.get("created_at")
                else datetime.utcnow()
            ),
            updated_at=(
                datetime.fromisoformat(payload["updated_at"])
                if payload.get("updated_at")
                else datetime.utcnow()
            ),
            messages=messages,
        )
