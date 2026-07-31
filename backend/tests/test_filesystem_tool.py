from __future__ import annotations

from pathlib import Path

import pytest

from backend.tools.filesystem_tool import FilesystemTool


def _tool(tmp_path: Path) -> FilesystemTool:
    return FilesystemTool(allowed_roots=[tmp_path])


def test_write_and_read_file(tmp_path: Path) -> None:
    tool = _tool(tmp_path)

    write_result = tool.execute(
        {
            "operation": "write_file",
            "path": "notes/hello.txt",
            "content": "hello world",
        }
    )
    read_result = tool.execute(
        {
            "operation": "read_file",
            "path": "notes/hello.txt",
        }
    )

    assert write_result["success"] is True
    assert read_result["success"] is True
    assert read_result["result"]["content"] == "hello world"


def test_rename_file(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    source = tmp_path / "a.txt"
    source.write_text("x", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "rename",
            "path": "a.txt",
            "new_name": "b.txt",
        }
    )

    assert result["success"] is True
    assert (tmp_path / "a.txt").exists() is False
    assert (tmp_path / "b.txt").exists() is True


def test_delete_file(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    target = tmp_path / "delete-me.txt"
    target.write_text("x", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "delete_file",
            "path": "delete-me.txt",
        }
    )

    assert result["success"] is True
    assert target.exists() is False


def test_move_file(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    source = tmp_path / "move.txt"
    source.write_text("move", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "move",
            "source": "move.txt",
            "destination": "nested/moved.txt",
        }
    )

    assert result["success"] is True
    assert (tmp_path / "move.txt").exists() is False
    assert (tmp_path / "nested" / "moved.txt").read_text(encoding="utf-8") == "move"


def test_copy_file(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    source = tmp_path / "copy.txt"
    source.write_text("copy", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "copy",
            "source": "copy.txt",
            "destination": "nested/copied.txt",
        }
    )

    assert result["success"] is True
    assert source.exists() is True
    assert (tmp_path / "nested" / "copied.txt").read_text(encoding="utf-8") == "copy"


def test_list_directory(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    result = tool.execute({"operation": "list_directory", "path": "."})

    assert result["success"] is True
    names = [item["name"] for item in result["result"]["entries"]]
    assert "a.txt" in names
    assert "b.txt" in names


def test_search_files(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "beta.txt").write_text("b", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "search_files",
            "path": ".",
            "pattern": "*.txt",
        }
    )

    assert result["success"] is True
    assert len(result["result"]["matches"]) == 2


def test_file_info(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    target = tmp_path / "info.txt"
    target.write_text("data", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "file_info",
            "path": "info.txt",
        }
    )

    assert result["success"] is True
    assert result["result"]["is_file"] is True
    assert result["result"]["size_bytes"] == 4


def test_blocked_parent_traversal(tmp_path: Path) -> None:
    tool = _tool(tmp_path)

    result = tool.execute(
        {
            "operation": "read_file",
            "path": "../escape.txt",
        }
    )

    assert result["success"] is False
    assert "Parent traversal" in result["error"]


def test_blocked_outside_root(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    result = tool.execute(
        {
            "operation": "read_file",
            "path": str(outside),
        }
    )

    assert result["success"] is False
    assert "outside allowed roots" in result["error"]


def test_validate_checks_supported_operation_and_path(tmp_path: Path) -> None:
    tool = _tool(tmp_path)

    with pytest.raises(Exception):
        tool.validate({"operation": "unknown", "path": "a.txt"})

    with pytest.raises(Exception):
        tool.validate({"operation": "read_file", "path": "../a.txt"})

    assert tool.validate({"operation": "create_directory", "path": "safe-dir"}) is True


def test_health_returns_healthy(tmp_path: Path) -> None:
    tool = _tool(tmp_path)

    assert tool.health() == {"status": "healthy"}
