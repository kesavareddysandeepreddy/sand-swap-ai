"""Production Python tool plugin with workspace sandbox enforcement."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.execution.recorder import ExecutionRecorder
from backend.tool_sdk.base_tool import BaseTool
from backend.tool_sdk.context import ToolContext
from backend.tool_sdk.decorator import tool


@tool(
    name="PythonTool",
    description="Sandboxed Python execution within the current workspace.",
    capabilities=["python"],
    priority=100,
)
class PythonTool(BaseTool):
    """Python execution tool constrained to a workspace root."""

    _DEFAULT_TIMEOUT_SECONDS = 30.0
    _default_execution_recorder: ExecutionRecorder | None = None

    _SANDBOX_BOOTSTRAP = """
import base64
import json
import os
import pathlib
import sys
import traceback

workspace = pathlib.Path(os.environ["PYTHON_TOOL_WORKSPACE_ROOT"]).resolve()
result_path = pathlib.Path(os.environ["PYTHON_TOOL_RESULT_PATH"]).resolve()
code = base64.b64decode(os.environ["PYTHON_TOOL_CODE_B64"]).decode("utf-8")

generated_files = set()


def _normalize_path(value):
    if value is None:
        return None
    try:
        candidate = pathlib.Path(str(value)).expanduser()
    except Exception:
        return None
    if not candidate.is_absolute():
        candidate = pathlib.Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _is_within_workspace(path):
    try:
        path.relative_to(workspace)
        return True
    except ValueError:
        return False


def _validate_path(value):
    normalized = _normalize_path(value)
    if normalized is None:
        return
    if not _is_within_workspace(normalized):
        raise PermissionError(f"Path outside allowed workspace: {normalized}")


def _capture_generated(value):
    normalized = _normalize_path(value)
    if normalized is None:
        return
    if _is_within_workspace(normalized):
        generated_files.add(str(normalized))


def _audit_hook(event, args):
    if event in {"subprocess.Popen", "os.system", "os.exec"}:
        raise PermissionError("Process execution is not allowed in PythonTool sandbox")
    if event == "os.chdir":
        _validate_path(args[0])
        return

    if event == "open":
        if args:
            mode = str(args[1]) if len(args) > 1 else "r"
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                _validate_path(args[0])
                _capture_generated(args[0])
        return

    if event == "os.open":
        if args:
            flags = int(args[1]) if len(args) > 1 else 0
            write_bits = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
            if flags & write_bits:
                _validate_path(args[0])
                _capture_generated(args[0])
        return

    if event in {
        "os.remove",
        "os.unlink",
        "os.rename",
        "os.replace",
        "os.mkdir",
        "os.makedirs",
        "os.rmdir",
        "os.symlink",
        "os.link",
        "pathlib.Path.mkdir",
        "pathlib.Path.write_text",
        "pathlib.Path.write_bytes",
        "shutil.copyfile",
        "shutil.copystat",
        "shutil.copytree",
        "shutil.move",
    }:
        if args:
            _validate_path(args[0])
            _capture_generated(args[0])
        if len(args) > 1:
            _validate_path(args[1])
            _capture_generated(args[1])


sys.addaudithook(_audit_hook)

globals_dict = {"__name__": "__main__", "__file__": "<python_tool>"}
exit_code = 0
try:
    compiled = compile(code, "<python_tool>", "exec")
    exec(compiled, globals_dict, globals_dict)
except Exception:
    traceback.print_exc()
    exit_code = 1
finally:
    payload = {"generated_files": sorted(generated_files)}
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload), encoding="utf-8")

if exit_code:
    sys.exit(exit_code)
"""

    def __init__(self, execution_recorder: ExecutionRecorder | None = None) -> None:
        self.execution_recorder = execution_recorder

    @classmethod
    def configure_execution_recorder(
        cls,
        execution_recorder: ExecutionRecorder,
    ) -> None:
        cls._default_execution_recorder = execution_recorder

    def name(self) -> str:
        return "PythonTool"

    def description(self) -> str:
        return "Sandboxed Python execution within the current workspace."

    def capabilities(self) -> list[str]:
        return ["python"]

    @staticmethod
    def _get_value(
        context: ToolContext | dict[str, Any], key: str, default: Any = None
    ) -> Any:
        return context.get(key, default)

    def _resolve_workspace_root(self, context: ToolContext | dict[str, Any]) -> Path:
        raw_root = self._get_value(context, "workspace_root")
        if not raw_root:
            roots = self._get_value(context, "workspace_roots") or self._get_value(
                context, "allowed_roots"
            )
            if isinstance(roots, list) and roots:
                raw_root = roots[0]

        if not raw_root:
            raw_root = os.getenv("WORKSPACE_ROOT", "") or str(Path.cwd())

        workspace_root = Path(str(raw_root)).expanduser().resolve(strict=False)
        if not workspace_root.exists():
            raise ValueError(f"Workspace root does not exist: {workspace_root}")
        if not workspace_root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {workspace_root}")
        return workspace_root

    @staticmethod
    def _ensure_within_workspace(path: Path, workspace_root: Path) -> None:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(f"Path outside workspace: {resolved}") from exc

    def _resolve_code(
        self, context: ToolContext | dict[str, Any], workspace_root: Path
    ) -> str:
        script_path = self._get_value(context, "script_path")
        if script_path:
            candidate = Path(str(script_path)).expanduser()
            if not candidate.is_absolute():
                candidate = workspace_root / candidate
            candidate = candidate.resolve(strict=True)
            self._ensure_within_workspace(candidate, workspace_root)
            if not candidate.is_file():
                raise ValueError(f"script_path is not a file: {candidate}")
            return candidate.read_text(encoding="utf-8")

        code = self._get_value(context, "code", "")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("PythonTool requires non-empty `code` or `script_path`.")
        return code

    @staticmethod
    def _extract_generated_files(
        result_file: Path, workspace_root: Path
    ) -> list[dict[str, Any]]:
        if not result_file.exists():
            return []

        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        raw_files = payload.get("generated_files", [])
        if not isinstance(raw_files, list):
            return []

        files: list[dict[str, Any]] = []
        for item in raw_files:
            path = Path(str(item)).resolve(strict=False)
            try:
                relative = str(path.relative_to(workspace_root))
            except ValueError:
                continue
            info = {
                "path": relative,
                "absolute_path": str(path),
                "exists": path.exists(),
            }
            if path.exists() and path.is_file():
                info["size_bytes"] = path.stat().st_size
            files.append(info)
        return files

    def _resolve_execution_recorder(
        self,
        context: ToolContext | dict[str, Any],
    ) -> ExecutionRecorder | None:
        if self.execution_recorder is not None:
            return self.execution_recorder
        if self._default_execution_recorder is not None:
            return self._default_execution_recorder
        recorder = self._get_value(context, "execution_recorder")
        if isinstance(recorder, ExecutionRecorder):
            return recorder
        return None

    def execute(self, context: ToolContext | dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()

        trace_id = self._get_value(context, "execution_trace_id")
        recorder = self._resolve_execution_recorder(context)
        trace = recorder.get_trace(str(trace_id)) if recorder and trace_id else None
        step = (
            trace.add_step("Python Tool Execution", metadata={"tool": self.name()})
            if trace is not None
            else None
        )

        try:
            workspace_root = self._resolve_workspace_root(context)
            code = self._resolve_code(context, workspace_root)
            timeout_seconds = float(
                self._get_value(
                    context, "timeout_seconds", self._DEFAULT_TIMEOUT_SECONDS
                )
            )
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be positive.")

            sandbox_root = workspace_root / ".sand_swap_python"
            sandbox_root.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                prefix="python_tool_result_",
                suffix=".json",
                delete=False,
                dir=sandbox_root,
            ) as handle:
                result_file = Path(handle.name)

            env = dict(os.environ)
            env["PYTHON_TOOL_WORKSPACE_ROOT"] = str(workspace_root)
            env["PYTHON_TOOL_RESULT_PATH"] = str(result_file)
            env["PYTHON_TOOL_CODE_B64"] = base64.b64encode(code.encode("utf-8")).decode(
                "ascii"
            )

            completed = subprocess.run(
                [sys.executable, "-I", "-c", self._SANDBOX_BOOTSTRAP],
                cwd=str(workspace_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            generated_files = self._extract_generated_files(result_file, workspace_root)
            result_file.unlink(missing_ok=True)
            execution_time = round(time.perf_counter() - started, 6)
            success = completed.returncode == 0

            result = {
                "success": success,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "generated_files": generated_files,
                "execution_time": execution_time,
            }

            if step is not None and trace is not None:
                metadata = {
                    "success": success,
                    "execution_time": execution_time,
                    "generated_file_count": len(generated_files),
                }
                if success:
                    trace.complete_step(step.id, metadata=metadata)
                else:
                    trace.fail_step(
                        step.id,
                        metadata={
                            **metadata,
                            "error": completed.stderr[-2000:],
                        },
                    )
            return result
        except subprocess.TimeoutExpired as exc:
            execution_time = round(time.perf_counter() - started, 6)
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            result = {
                "success": False,
                "stdout": stdout,
                "stderr": f"Execution timed out after {exc.timeout} seconds.\n{stderr}",
                "generated_files": [],
                "execution_time": execution_time,
            }
            if step is not None and trace is not None:
                trace.fail_step(
                    step.id,
                    metadata={
                        "success": False,
                        "execution_time": execution_time,
                        "error": "timeout",
                    },
                )
            return result
        except Exception as exc:  # noqa: BLE001
            execution_time = round(time.perf_counter() - started, 6)
            result = {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "generated_files": [],
                "execution_time": execution_time,
            }
            if step is not None and trace is not None:
                trace.fail_step(
                    step.id,
                    metadata={
                        "success": False,
                        "execution_time": execution_time,
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )
            return result
