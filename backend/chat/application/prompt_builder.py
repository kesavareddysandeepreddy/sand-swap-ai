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
            lines.append("Known user facts:")
            for memory in context.memories:
                value = memory.value
                if memory.key.strip().lower() == "name":
                    value = str(memory.value).strip().title()
                lines.append(f"- {memory.key}: {value}")
            lines.append("")

        documents = getattr(context, "documents", [])

        if documents:
            lines.append("Knowledge context:")
            for chunk in documents:
                section = str(chunk.metadata.get("section", "")).strip()
                if section and section != "-":
                    lines.append(f"Source: {chunk.document_name} | Section: {section}")
                else:
                    lines.append(f"Source: {chunk.document_name}")
                lines.append(chunk.text)
            lines.append("")

        if context.history:
            lines.append("Conversation history:")
            for message in context.history:
                lines.append(f"{message.role}: {message.content}")
            lines.append("")

        knowledge_context = getattr(context, "knowledge_context", "")
        multimodal_context = getattr(context, "multimodal_context", "")
        injected_context = knowledge_context or multimodal_context
        if injected_context:
            lines.append("Multimodal context:")
            lines.append(injected_context)
            lines.append("")

        lines.append(f"User question: {PromptManager.chat(context.current_message)}")
        return "\n".join(lines)

    def build_system_prompt(self) -> str:
        """Return the system prompt for chat responses."""
        return (
            "You are a helpful AI assistant. Answer clearly, concisely, and naturally using Markdown: "
            "short paragraphs, bullet lists, numbered steps, and bold for important entities where useful. "
            "For general questions (e.g. Kubernetes, Python, OAuth2, Git) answer directly from your knowledge — "
            "do NOT refuse or say no context is available. "
            "When retrieved documents or repository chunks are provided in the prompt, treat them as the "
            "primary source of truth for questions about that private knowledge and blend them naturally "
            "with your general knowledge when relevant. "
            "When known user facts are provided, use them naturally in your answer and do not claim you "
            "cannot remember user details. "
            "Never say you cannot answer simply because retrieval returned no documents."
        )
