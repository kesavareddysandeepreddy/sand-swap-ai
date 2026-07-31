"""Filesystem Tool SDK plugin with workspace-root safety constraints."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.tool_sdk.base_tool import BaseTool
from backend.tool_sdk.context import ToolContext
from backend.tool_sdk.decorator import tool


class FilesystemToolError(Exception):
    """Raised when a filesystem tool request is invalid or unsafe."""


@tool(
    name="FilesystemTool",
    description="Safe local file operations within configured workspace roots.",
    capabilities=["filesystem"],
    priority=100,
)
class FilesystemTool(BaseTool):
    """Filesystem plugin restricted to configured workspace roots."""

    _SUPPORTED_OPERATIONS: set[str] = {
        "read_file",
        "write_file",
        "list_directory",
        "search_files",
        "create_directory",
        "delete_file",
        "rename",
        "move",
        "copy",
        "file_info",
    }

    def __init__(self, allowed_roots: list[str | Path] | None = None) -> None:
        self._allowed_roots_override = allowed_roots

    def name(self) -> str:
        return "FilesystemTool"

    def description(self) -> str:
        return "Safe local file operations within configured workspace roots."

    def capabilities(self) -> list[str]:
        return ["filesystem"]

    def validate(
        self,
        context: ToolContext | dict[str, Any] | None = None,
    ) -> bool:
        """Validate operation support and path constraints."""
        payload = context or {}
        operation = str(payload.get("operation", "")).strip()
        if operation not in self._SUPPORTED_OPERATIONS:
            raise FilesystemToolError(f"Unsupported operation: {operation}")

        roots = self._get_allowed_roots(payload)
        if not roots:
            raise FilesystemToolError("No allowed workspace roots are configured.")

        if operation in {
            "read_file",
            "write_file",
            "list_directory",
            "search_files",
            "create_directory",
            "delete_file",
            "file_info",
        }:
            self._resolve_path(str(payload.get("path", "")), roots, must_exist=False)
        elif operation == "rename":
            self._resolve_path(str(payload.get("path", "")), roots, must_exist=False)
            self._validate_new_name(str(payload.get("new_name", "")))
        elif operation in {"move", "copy"}:
            self._resolve_path(str(payload.get("source", "")), roots, must_exist=False)
            self._resolve_path(
                str(payload.get("destination", "")),
                roots,
                must_exist=False,
            )
        return True

    def health(self) -> dict[str, object]:
        return {"status": "healthy"}

    def execute(self, context: ToolContext | dict[str, Any]) -> dict[str, Any]:
        operation = str(context.get("operation", "")).strip()
        try:
            self.validate(context)
            roots = self._get_allowed_roots(context)
            handler_name = f"_op_{operation}"
            handler = getattr(self, handler_name, None)
            if not callable(handler):
                raise FilesystemToolError(f"Unsupported operation: {operation}")
            return handler(context, roots)
        except Exception as exc:  # noqa: BLE001
            path_hint = str(
                context.get("path")
                or context.get("source")
                or context.get("destination")
                or ""
            )
            return {
                "success": False,
                "operation": operation,
                "path": path_hint,
                "error": str(exc),
            }

    def _get_allowed_roots(self, context: ToolContext | dict[str, Any]) -> list[Path]:
        if self._allowed_roots_override is not None:
            raw_roots = [str(item) for item in self._allowed_roots_override]
        else:
            from_context = context.get("workspace_roots") or context.get(
                "allowed_roots"
            )
            if isinstance(from_context, list):
                raw_roots = [str(item) for item in from_context if str(item).strip()]
            else:
                env_roots = (
                    os.getenv("FILESYSTEM_TOOL_ALLOWED_ROOTS")
                    or os.getenv("WORKSPACE_ROOTS")
                    or ""
                )
                raw_roots = [
                    item for item in env_roots.split(os.pathsep) if item.strip()
                ]

        if not raw_roots:
            raw_roots = [str(Path.cwd())]
        return [Path(item).resolve(strict=False) for item in raw_roots]

    @staticmethod
    def _contains_parent_traversal(raw_path: str) -> bool:
        return ".." in Path(raw_path).parts

    def _resolve_path(
        self,
        raw_path: str,
        roots: list[Path],
        *,
        must_exist: bool,
    ) -> Path:
        normalized = raw_path.strip()
        if not normalized:
            raise FilesystemToolError("Path is required.")
        if self._contains_parent_traversal(normalized):
            raise FilesystemToolError("Parent traversal is not allowed.")

        requested = Path(normalized)
        candidates: list[Path]
        if requested.is_absolute():
            candidates = [requested]
        elif must_exist:
            candidates = [root / requested for root in roots]
        else:
            candidates = [roots[0] / requested]

        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=must_exist)
            except FileNotFoundError:
                continue
            if any(self._is_within_root(resolved, root) for root in roots):
                return resolved

        if must_exist:
            raise FilesystemToolError(
                f"Path does not exist within allowed roots: {raw_path}"
            )
        raise FilesystemToolError(f"Path is outside allowed roots: {raw_path}")

    @staticmethod
    def _is_within_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _validate_new_name(new_name: str) -> None:
        normalized = new_name.strip()
        if not normalized:
            raise FilesystemToolError("new_name is required for rename operation.")
        new_name_path = Path(normalized)
        if new_name_path.is_absolute() or len(new_name_path.parts) != 1:
            raise FilesystemToolError(
                "new_name must be a single file or directory name."
            )
        if ".." in new_name_path.parts:
            raise FilesystemToolError("Parent traversal is not allowed in new_name.")

    @staticmethod
    def _ok(operation: str, path: str, result: Any) -> dict[str, Any]:
        return {
            "success": True,
            "operation": operation,
            "path": path,
            "result": result,
        }

    def _op_read_file(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=True)
        if not path.is_file():
            raise FilesystemToolError("Path is not a file.")
        content = path.read_text(encoding="utf-8")
        return self._ok("read_file", str(path), {"content": content})

    def _op_write_file(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=False)
        content = str(context.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self._ok(
            "write_file",
            str(path),
            {"bytes_written": len(content.encode("utf-8"))},
        )

    def _op_list_directory(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(
            str(context.get("path", ".")),
            roots,
            must_exist=True,
        )
        if not path.is_dir():
            raise FilesystemToolError("Path is not a directory.")
        entries: list[dict[str, Any]] = []
        for item in sorted(path.iterdir(), key=lambda entry: entry.name):
            entries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                }
            )
        return self._ok("list_directory", str(path), {"entries": entries})

    def _op_search_files(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(
            str(context.get("path", ".")),
            roots,
            must_exist=True,
        )
        pattern = str(context.get("pattern", "")).strip()
        if not pattern:
            raise FilesystemToolError("pattern is required for search_files operation.")
        if not path.is_dir():
            raise FilesystemToolError("Search path must be a directory.")

        matches: list[str] = []
        for item in path.rglob(pattern):
            resolved = item.resolve(strict=False)
            if any(self._is_within_root(resolved, root) for root in roots):
                matches.append(str(resolved))
        matches.sort()
        return self._ok(
            "search_files", str(path), {"matches": matches, "pattern": pattern}
        )

    def _op_create_directory(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=False)
        path.mkdir(parents=True, exist_ok=True)
        return self._ok("create_directory", str(path), {"created": True})

    def _op_delete_file(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=True)
        if not path.is_file():
            raise FilesystemToolError("delete_file only supports files.")
        path.unlink()
        return self._ok("delete_file", str(path), {"deleted": True})

    def _op_rename(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=True)
        new_name = str(context.get("new_name", ""))
        self._validate_new_name(new_name)
        destination = path.parent / new_name
        destination = self._resolve_path(str(destination), roots, must_exist=False)
        renamed = path.rename(destination)
        return self._ok(
            "rename",
            str(path),
            {"new_path": str(renamed)},
        )

    def _op_move(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        source = self._resolve_path(
            str(context.get("source", "")), roots, must_exist=True
        )
        destination = self._resolve_path(
            str(context.get("destination", "")),
            roots,
            must_exist=False,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        moved = Path(shutil.move(str(source), str(destination)))
        moved = moved.resolve(strict=True)
        if not any(self._is_within_root(moved, root) for root in roots):
            raise FilesystemToolError(
                "Move destination resolved outside allowed roots."
            )
        return self._ok(
            "move",
            str(source),
            {"destination": str(moved)},
        )

    def _op_copy(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        source = self._resolve_path(
            str(context.get("source", "")), roots, must_exist=True
        )
        destination = self._resolve_path(
            str(context.get("destination", "")),
            roots,
            must_exist=False,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)

        if source.is_dir():
            copied = Path(shutil.copytree(source, destination, dirs_exist_ok=True))
        else:
            copied = Path(shutil.copy2(source, destination))
        copied = copied.resolve(strict=True)
        if not any(self._is_within_root(copied, root) for root in roots):
            raise FilesystemToolError(
                "Copy destination resolved outside allowed roots."
            )
        return self._ok(
            "copy",
            str(source),
            {"destination": str(copied)},
        )

    def _op_file_info(
        self,
        context: ToolContext | dict[str, Any],
        roots: list[Path],
    ) -> dict[str, Any]:
        path = self._resolve_path(str(context.get("path", "")), roots, must_exist=True)
        stats = path.stat()
        result = {
            "exists": True,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "size_bytes": stats.st_size,
            "modified_at": datetime.fromtimestamp(stats.st_mtime, tz=UTC).isoformat(),
            "created_at": datetime.fromtimestamp(stats.st_ctime, tz=UTC).isoformat(),
        }
        return self._ok("file_info", str(path), result)
