from __future__ import annotations

from backend.project_memory.archive_manager import ArchiveManager
from backend.project_memory.checkpoint import ConversationCheckpointEngine
from backend.project_memory.repository import ConversationArchiveRepository
from backend.project_memory.summarizer import ConversationSummarizer


def _engine(interval: int = 3) -> tuple[ConversationCheckpointEngine, ArchiveManager]:
    repository = ConversationArchiveRepository()
    manager = ArchiveManager(repository=repository, summarizer=ConversationSummarizer())
    engine = ConversationCheckpointEngine(
        archive_manager=manager,
        checkpoint_interval=interval,
    )
    return engine, manager


def test_should_not_checkpoint_below_interval() -> None:
    engine, manager = _engine(interval=3)

    assert engine.should_checkpoint(2) is False
    result = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2"],
    )

    assert result is None
    assert manager._repository.get("project-1", "conversation-1") == []


def test_checkpoint_exactly_interval() -> None:
    engine, manager = _engine(interval=3)

    result = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3"],
    )

    assert result is not None
    assert result.sequence == 1
    assert manager._repository.get("project-1", "conversation-1")


def test_checkpoint_above_interval() -> None:
    engine, manager = _engine(interval=3)

    result = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3", "m4"],
    )

    assert result is not None
    assert result.sequence == 1
    assert len(manager._repository.get("project-1", "conversation-1")) == 1


def test_multiple_checkpoints_increment_sequence() -> None:
    engine, manager = _engine(interval=3)

    first = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3"],
    )
    second = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3", "m4", "m5", "m6"],
    )

    assert first is not None
    assert second is not None
    assert first.sequence == 1
    assert second.sequence == 2


def test_no_duplicate_checkpoint_for_same_message_range() -> None:
    engine, manager = _engine(interval=3)

    first = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3"],
    )
    duplicate = engine.create_checkpoint(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["m1", "m2", "m3"],
    )

    assert first is not None
    assert duplicate is None
    assert len(manager._repository.get("project-1", "conversation-1")) == 1
