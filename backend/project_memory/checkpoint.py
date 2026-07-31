"""Automatic conversation checkpoint engine."""

from __future__ import annotations

from collections.abc import Sequence

from backend.project_memory.archive_manager import ArchiveManager
from backend.project_memory.models import ConversationSummary


class ConversationCheckpointEngine:
    """Creates periodic conversation summary checkpoints."""

    def __init__(
        self,
        archive_manager: ArchiveManager,
        checkpoint_interval: int = 200,
    ) -> None:
        if checkpoint_interval <= 0:
            raise ValueError("checkpoint_interval must be greater than zero.")
        self._archive_manager = archive_manager
        self._checkpoint_interval = checkpoint_interval
        self._last_checkpoint_counts: dict[tuple[str, str], int] = {}

    def should_checkpoint(self, message_count: int) -> bool:
        """Return whether a checkpoint should be created for message count."""
        return message_count >= self._checkpoint_interval

    def create_checkpoint(
        self,
        project_id: str,
        conversation_id: str,
        messages: Sequence[str],
    ) -> ConversationSummary | None:
        """Create checkpoint summary if interval reached and not already checkpointed."""
        message_count = len(messages)
        if not self.should_checkpoint(message_count):
            return None

        key = (project_id, conversation_id)
        last_count = self._last_checkpoint_counts.get(key, 0)
        if last_count == message_count:
            return None

        summary = self._archive_manager.archive(
            project_id=project_id,
            conversation_id=conversation_id,
            messages=messages,
        )
        self._last_checkpoint_counts[key] = message_count
        return summary
