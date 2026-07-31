from __future__ import annotations

from backend.tool_sdk.context import ToolContext


def test_tool_context_default_construction() -> None:
    context = ToolContext()

    assert context.project_id == ""
    assert context.conversation_id == ""
    assert context.user_id == ""
    assert context.workspace_id == ""
    assert context.attachments == ()
    assert context.variables == {}
    assert context.metadata == {}
    assert context.execution_trace_id is None


def test_tool_context_custom_values() -> None:
    context = ToolContext(
        project_id="project-1",
        conversation_id="conversation-1",
        user_id="user-1",
        workspace_id="workspace-1",
        attachments=("file-a.png", "file-b.txt"),
        variables={"operation": "read_file"},
        metadata={"request_id": "req-1"},
        execution_trace_id="trace-1",
    )

    assert context.project_id == "project-1"
    assert context.conversation_id == "conversation-1"
    assert context.user_id == "user-1"
    assert context.workspace_id == "workspace-1"
    assert context.attachments == ("file-a.png", "file-b.txt")
    assert context.variables == {"operation": "read_file"}
    assert context.metadata == {"request_id": "req-1"}
    assert context.execution_trace_id == "trace-1"


def test_tool_context_metadata_updates() -> None:
    context = ToolContext(metadata={"phase": "start"})

    context.metadata["phase"] = "done"
    context.metadata["duration_ms"] = 10

    assert context.metadata["phase"] == "done"
    assert context.metadata["duration_ms"] == 10


def test_tool_context_attachment_storage_is_tuple() -> None:
    context = ToolContext(attachments=("a.png", "b.pdf"))

    assert isinstance(context.attachments, tuple)
    assert context.attachments == ("a.png", "b.pdf")
