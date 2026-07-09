"""Prompt construction for chat requests."""

from __future__ import annotations

from backend.chat.application.context_builder import PromptContext
from backend.llm.prompt_manager import PromptManager


class PromptBuilder:
    """Build the prompt sent to the language model."""

    def build_prompt(self, context: PromptContext) -> str:
        """Build a prompt that includes memories, documents, history, and latest message."""
        lines: list[str] = []

        if context.memories:
            lines.append("Relevant memories:")
            for memory in context.memories:
                lines.append(f"- {memory.key}: {memory.value}")
            lines.append("")

        documents = getattr(context, "documents", [])
        citations = getattr(context, "document_citations", [])

        if documents:
            lines.append("Relevant retrieved documents:")
            for chunk in documents:
                section = chunk.metadata.get("section", "-")
                page = chunk.metadata.get("page", "-")
                lines.append(
                    f"- [{chunk.document_name}] (chunk={chunk.chunk_id}, page={page}, section={section})"
                )
                lines.append(chunk.text)
            lines.append("")

        if citations:
            lines.append("Citations:")
            for citation in citations:
                lines.append(f"- {citation}")
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
