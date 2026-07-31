"""Conversation archive manager for project-level summary storage."""

from __future__ import annotations

from collections.abc import Sequence

from backend.project_memory.models import ConversationSummary
from backend.project_memory.repository import ConversationArchiveRepository
from backend.project_memory.summarizer import ConversationSummarizer


class ArchiveManager:
    """Coordinates summary generation and in-memory archival."""

    def __init__(
        self,
        repository: ConversationArchiveRepository,
        summarizer: ConversationSummarizer,
    ) -> None:
        self._repository = repository
        self._summarizer = summarizer

    def archive(
        self,
        project_id: str,
        conversation_id: str,
        messages: Sequence[str],
    ) -> ConversationSummary:
        """Generate and save one archived conversation summary."""
        existing = self._repository.get(project_id, conversation_id)
        next_sequence = 1 if not existing else existing[-1].sequence + 1

        generated = self._summarizer.summarize(messages)
        summary = ConversationSummary(
            project_id=project_id,
            conversation_id=conversation_id,
            sequence=next_sequence,
            title=generated.title,
            summary=generated.summary,
            key_topics=list(generated.key_topics),
        )
        return self._repository.save(summary)
