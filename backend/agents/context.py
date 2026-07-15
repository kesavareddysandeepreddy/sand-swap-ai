"""Agent execution context model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.chat.domain.conversation import Conversation


@dataclass(slots=True)
class AgentExecutionContext:
    """Canonical context passed to planner and agents."""

    conversation: "Conversation"
    workspace_id: str | None
    project_id: str | None
    knowledge_object_ids: list[str] = field(default_factory=list)
    knowledge_context: str = ""
    memory_context: list[Any] = field(default_factory=list)
    rag_context: list[Any] = field(default_factory=list)
    vision_context: str = ""
    user_prompt: str = ""
    prompt: str = ""
    system_prompt: str = ""
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
