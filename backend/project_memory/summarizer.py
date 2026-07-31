"""Conversation summarizer foundation with deterministic placeholder behavior."""

from __future__ import annotations

from collections.abc import Sequence

from backend.project_memory.models import ConversationSummary


class ConversationSummarizer:
    """Builds a simple summary using first and last messages."""

    def summarize(self, messages: Sequence[str]) -> ConversationSummary:
        """Create a placeholder summary from message boundaries.

        Args:
            messages: Ordered conversation message texts.

        Returns:
            ConversationSummary: Deterministic placeholder summary object.
        """
        normalized = [item.strip() for item in messages if item and item.strip()]

        if not normalized:
            return ConversationSummary(
                title="Empty conversation",
                summary="No messages available to summarize.",
                key_topics=[],
            )

        first = normalized[0]
        last = normalized[-1]
        topic_seed = self._extract_topics(first, last)

        if len(normalized) == 1:
            title = self._clip(first, 60)
            summary_text = (
                f"Conversation started and ended with: {self._clip(first, 120)}"
            )
        else:
            title = self._clip(first, 60)
            summary_text = (
                "Conversation evolved from "
                f"'{self._clip(first, 80)}' to '{self._clip(last, 80)}'."
            )

        return ConversationSummary(
            title=title,
            summary=summary_text,
            key_topics=topic_seed,
        )

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."

    @staticmethod
    def _extract_topics(first: str, last: str) -> list[str]:
        words: list[str] = []
        for token in f"{first} {last}".split():
            cleaned = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_"})
            lowered = cleaned.lower()
            if len(lowered) >= 4 and lowered not in words:
                words.append(lowered)
            if len(words) == 5:
                break
        return words
