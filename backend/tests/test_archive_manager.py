from __future__ import annotations

from backend.project_memory.archive_manager import ArchiveManager
from backend.project_memory.repository import ConversationArchiveRepository
from backend.project_memory.summarizer import ConversationSummarizer


def _manager() -> tuple[ArchiveManager, ConversationArchiveRepository]:
    repository = ConversationArchiveRepository()
    manager = ArchiveManager(repository=repository, summarizer=ConversationSummarizer())
    return manager, repository


def test_archive_creation() -> None:
    manager, repository = _manager()

    archived = manager.archive(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["Start planning release.", "Confirm release milestones."],
    )

    assert archived.project_id == "project-1"
    assert archived.conversation_id == "conversation-1"
    assert archived.sequence == 1
    assert archived.title
    assert archived.summary
    assert len(repository.get("project-1", "conversation-1")) == 1


def test_sequence_increment() -> None:
    manager, repository = _manager()

    first = manager.archive(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["Initial goals.", "Discuss architecture."],
    )
    second = manager.archive(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["Refine details.", "Finalize scope."],
    )

    assert first.sequence == 1
    assert second.sequence == 2
    records = repository.get("project-1", "conversation-1")
    assert [item.sequence for item in records] == [1, 2]


def test_latest_returns_newest_for_project() -> None:
    manager, repository = _manager()

    first = manager.archive(
        project_id="project-1",
        conversation_id="conversation-a",
        messages=["Plan A.", "Close A."],
    )
    second = manager.archive(
        project_id="project-1",
        conversation_id="conversation-b",
        messages=["Plan B.", "Close B."],
    )

    latest = repository.latest("project-1")

    assert latest is not None
    assert latest.id == second.id
    assert latest.id != first.id


def test_list_returns_project_entries() -> None:
    manager, repository = _manager()

    manager.archive(
        project_id="project-1",
        conversation_id="conversation-a",
        messages=["A1", "A2"],
    )
    manager.archive(
        project_id="project-1",
        conversation_id="conversation-b",
        messages=["B1", "B2"],
    )
    manager.archive(
        project_id="project-2",
        conversation_id="conversation-x",
        messages=["X1", "X2"],
    )

    listed = repository.list("project-1")

    assert len(listed) == 2
    assert {item.project_id for item in listed} == {"project-1"}
    assert {item.conversation_id for item in listed} == {
        "conversation-a",
        "conversation-b",
    }


def test_empty_archive_behavior() -> None:
    repository = ConversationArchiveRepository()

    assert repository.get("project-1", "conversation-1") == []
    assert repository.list("project-1") == []
    assert repository.latest("project-1") is None


def test_clear_removes_all_entries() -> None:
    manager, repository = _manager()

    manager.archive(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=["Message one.", "Message two."],
    )
    assert repository.list("project-1")

    repository.clear()

    assert repository.list("project-1") == []
    assert repository.latest("project-1") is None
