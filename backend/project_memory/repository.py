"""In-memory repository for archived conversation summaries."""

from __future__ import annotations

from collections import defaultdict

from backend.project_memory.models import ConversationSummary


class ConversationArchiveRepository:
    """Stores conversation summaries in memory grouped by project and conversation."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, list[ConversationSummary]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def save(self, summary: ConversationSummary) -> ConversationSummary:
        """Persist one summary entry in memory."""
        self._records[summary.project_id][summary.conversation_id].append(summary)
        return summary

    def get(self, project_id: str, conversation_id: str) -> list[ConversationSummary]:
        """Return summaries for one conversation in sequence order."""
        records = self._records.get(project_id, {}).get(conversation_id, [])
        return sorted(records, key=lambda item: item.sequence)

    def list(self, project_id: str) -> list[ConversationSummary]:
        """Return all archived summaries for one project."""
        project_records = self._records.get(project_id, {})
        flattened = [
            item
            for conversation_records in project_records.values()
            for item in conversation_records
        ]
        return sorted(
            flattened,
            key=lambda item: (item.conversation_id, item.sequence),
        )

    def latest(self, project_id: str) -> ConversationSummary | None:
        """Return the latest archived summary in the project."""
        project_entries = self.list(project_id)
        if not project_entries:
            return None
        return max(project_entries, key=lambda item: item.created_at)

    def clear(self) -> None:
        """Remove all in-memory archive records."""
        self._records.clear()
