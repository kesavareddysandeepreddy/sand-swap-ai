"""Prompt construction for chat requests."""

from __future__ import annotations

from backend.chat.application.context_builder import PromptContext
from backend.llm.prompt_manager import PromptManager


class PromptBuilder:
    """Build the prompt sent to the language model."""

    def build_prompt(self, context: PromptContext) -> str:
        """Build a prompt that includes history, memories, and the latest message."""
        lines: list[str] = []

        if context.memories:
            lines.append("Relevant memories:")
            for memory in context.memories:
                lines.append(f"- {memory.key}: {memory.value}")
            lines.append("")

        if context.history:
            lines.append("Recent conversation:")
            for message in context.history:
                lines.append(f"{message.role}: {message.content}")
            lines.append("")

        lines.append(f"User request: {PromptManager.chat(context.current_message)}")
        return "\n".join(lines)

    def build_system_prompt(self) -> str:
        """Return the system prompt for chat responses."""
        return "You are a helpful assistant. Respond clearly and concisely."
