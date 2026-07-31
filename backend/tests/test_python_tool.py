from __future__ import annotations

from pathlib import Path

from backend.execution.recorder import ExecutionRecorder
from backend.tools.python_tool import PythonTool


def test_python_tool_successful_execution(tmp_path: Path) -> None:
    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": "print('hello python tool')",
        }
    )

    assert result["success"] is True
    assert "hello python tool" in result["stdout"]
    assert result["stderr"] == ""
    assert result["generated_files"] == []
    assert result["execution_time"] >= 0.0


def test_python_tool_runtime_exception(tmp_path: Path) -> None:
    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": "raise RuntimeError('boom')",
        }
    )

    assert result["success"] is False
    assert "RuntimeError: boom" in result["stderr"]


def test_python_tool_syntax_error(tmp_path: Path) -> None:
    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": "def bad(:\n    pass",
        }
    )

    assert result["success"] is False
    assert "SyntaxError" in result["stderr"]


def test_python_tool_generated_files(tmp_path: Path) -> None:
    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": (
                "from pathlib import Path\n"
                "Path('out').mkdir(exist_ok=True)\n"
                "Path('out/data.json').write_text('{\\\"ok\\\": true}', encoding='utf-8')\n"
                "print('done')\n"
            ),
        }
    )

    assert result["success"] is True
    assert any(item["path"] == "out/data.json" for item in result["generated_files"])


def test_python_tool_timeout(tmp_path: Path) -> None:
    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": "import time\ntime.sleep(2)\nprint('late')",
            "timeout_seconds": 0.2,
        }
    )

    assert result["success"] is False
    assert "timed out" in result["stderr"].lower()


def test_python_tool_workspace_restriction(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    if outside.exists():
        outside.unlink()

    tool = PythonTool()
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": (
                "from pathlib import Path\n"
                "Path('../outside.txt').write_text('x', encoding='utf-8')\n"
            ),
        }
    )

    assert result["success"] is False
    assert "outside allowed workspace" in result["stderr"].lower()
    assert not outside.exists()


def test_python_tool_records_execution_trace_step(tmp_path: Path) -> None:
    recorder = ExecutionRecorder()
    trace = recorder.create_trace(worker_name="universal_worker", request_id="req-1")

    tool = PythonTool(execution_recorder=recorder)
    result = tool.execute(
        {
            "workspace_root": str(tmp_path),
            "code": "print('trace')",
            "execution_trace_id": trace.trace_id,
        }
    )

    assert result["success"] is True
    updated = recorder.get_trace(trace.trace_id)
    assert updated is not None
    step = updated.steps[-1]
    assert step.stage == "Python Tool Execution"
    assert step.status == "completed"
    assert step.metadata["success"] is True


def test_python_tool_reads_script_path_within_workspace(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('from script')\n", encoding="utf-8")

    tool = PythonTool()
    result = tool.execute({"workspace_root": str(tmp_path), "script_path": str(script)})

    assert result["success"] is True
    assert "from script" in result["stdout"]
