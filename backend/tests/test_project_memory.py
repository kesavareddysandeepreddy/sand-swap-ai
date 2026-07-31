from __future__ import annotations

from datetime import datetime

from backend.project_memory.models import (
    ConversationSummary,
    DecisionRecord,
    ProjectMemorySummary,
)
from backend.project_memory.summarizer import ConversationSummarizer


def test_conversation_summary_model_creation() -> None:
    record = ConversationSummary(
        project_id="project-1",
        conversation_id="conversation-1",
        sequence=2,
        title="Sprint planning",
        summary="Discussion about sprint scope and delivery timelines.",
        key_topics=["sprint", "scope", "timeline"],
    )

    assert record.id
    assert record.project_id == "project-1"
    assert record.conversation_id == "conversation-1"
    assert record.sequence == 2
    assert record.title == "Sprint planning"
    assert "delivery" in record.summary
    assert record.key_topics == ["sprint", "scope", "timeline"]
    assert isinstance(record.created_at, datetime)


def test_decision_record_model_creation() -> None:
    decision = DecisionRecord(
        project_id="project-1",
        title="Use SQLite for local mode",
        decision="Adopt SQLite as the default local store.",
        reason="Reduces setup complexity for local-first development.",
        tags=["database", "local-first"],
    )

    assert decision.id
    assert decision.project_id == "project-1"
    assert decision.title == "Use SQLite for local mode"
    assert "default local store" in decision.decision
    assert "setup complexity" in decision.reason
    assert decision.tags == ["database", "local-first"]
    assert isinstance(decision.created_at, datetime)


def test_project_memory_summary_model_creation() -> None:
    summary = ProjectMemorySummary(
        total_conversations=8,
        total_decisions=3,
    )

    assert summary.total_conversations == 8
    assert summary.total_decisions == 3
    assert isinstance(summary.last_updated, datetime)


def test_summarizer_output_from_messages() -> None:
    summarizer = ConversationSummarizer()
    output = summarizer.summarize(
        [
            "Discuss memory architecture for project.",
            "Capture key decisions and store in summaries.",
            "Finalize additive rollout and tests.",
        ]
    )

    assert isinstance(output, ConversationSummary)
    assert output.title
    assert output.summary
    assert output.summary.startswith("Conversation evolved")
    assert len(output.key_topics) > 0


def test_summarizer_handles_empty_conversation() -> None:
    summarizer = ConversationSummarizer()
    output = summarizer.summarize([])

    assert output.title == "Empty conversation"
    assert output.summary == "No messages available to summarize."
    assert output.key_topics == []
