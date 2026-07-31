"""Task-plan driven tool invocation engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.execution.models import ExecutionTrace
from backend.execution.tracker import ExecutionTracker
from backend.task_planner.models import TaskPlan, TaskStep
from backend.tool_execution.executor import ToolExecutor
from backend.tool_execution.resolver import ToolResolver
from backend.tool_execution.result import ToolExecutionResult
from backend.workflows.context import WorkflowContext


class ToolInvocationEngine:
    """Execute task-plan steps using resolved tools and record results."""

    def __init__(
        self, resolver: ToolResolver, executor: ToolExecutor | None = None
    ) -> None:
        self.resolver = resolver
        self.executor = executor or ToolExecutor()

    @staticmethod
    def _workspace_root(context: WorkflowContext) -> Path:
        raw_root = context.agent_context.metadata.get("workspace_root")
        if raw_root:
            return Path(str(raw_root)).expanduser().resolve(strict=False)
        return Path.cwd().resolve()

    @staticmethod
    def _summarize_tools(results: list[ToolExecutionResult]) -> str:
        if not results:
            return "No tool outputs were produced."

        lines = ["Tool outputs:"]
        for result in results:
            lines.append(
                f"- {result.tool_name}: {'success' if result.success else 'failed'}"
            )
            if result.stdout:
                lines.append(f"  stdout: {result.stdout[:1000]}")
            if result.stderr:
                lines.append(f"  stderr: {result.stderr[:1000]}")
        return "\n".join(lines)

    @staticmethod
    def _is_expression(prompt: str) -> bool:
        return bool(re.fullmatch(r"[0-9\s\+\-\*\/\(\)\.]+", prompt.strip()))

    @staticmethod
    def _extract_code(prompt: str) -> str:
        fenced = re.search(
            r"```(?:python)?\s*(.*?)```", prompt, re.DOTALL | re.IGNORECASE
        )
        if fenced:
            return fenced.group(1).strip()
        if ToolInvocationEngine._is_expression(prompt):
            return f"print({prompt.strip()})"
        return prompt.strip()

    @staticmethod
    def _filesystem_payload(step: TaskStep, context: WorkflowContext) -> dict[str, Any]:
        prompt = context.agent_context.user_prompt.lower()
        target = (step.target or "").strip() or prompt.strip()
        operation = "read_file"
        if any(token in prompt for token in ["create", "make", "write", "save"]):
            operation = "write_file"
        elif any(token in prompt for token in ["list", "show", "find", "search"]):
            operation = "search_files"

        payload: dict[str, Any] = {
            "operation": operation,
            "workspace_roots": [str(ToolInvocationEngine._workspace_root(context))],
            "execution_trace_id": context.agent_context.metadata.get(
                "execution_trace_id"
            ),
        }
        if operation == "write_file":
            path = target if target else "output.txt"
            payload.update({"path": path, "content": context.agent_context.user_prompt})
        elif operation == "search_files":
            payload.update(
                {"path": ".", "pattern": "*.pdf" if "pdf" in prompt else "*"}
            )
        else:
            payload.update({"path": target})
        return payload

    @staticmethod
    def _python_payload(step: TaskStep, context: WorkflowContext) -> dict[str, Any]:
        workspace_root = ToolInvocationEngine._workspace_root(context)
        return {
            "workspace_root": str(workspace_root),
            "code": ToolInvocationEngine._extract_code(
                context.agent_context.user_prompt
            ),
            "timeout_seconds": context.agent_context.metadata.get(
                "python_timeout_seconds", 30
            ),
            "execution_trace_id": context.agent_context.metadata.get(
                "execution_trace_id"
            ),
        }

    @staticmethod
    def _rest_payload(step: TaskStep, context: WorkflowContext) -> dict[str, Any]:
        prompt = context.agent_context.user_prompt.strip()
        url_match = re.search(r"https?://\S+", prompt)
        return {
            "url": url_match.group(0) if url_match else prompt,
            "method": "GET",
            "workspace_root": str(ToolInvocationEngine._workspace_root(context)),
            "execution_trace_id": context.agent_context.metadata.get(
                "execution_trace_id"
            ),
        }

    @staticmethod
    def _mcp_payload(step: TaskStep, context: WorkflowContext) -> dict[str, Any]:
        return {
            "server_name": step.target
            or context.agent_context.metadata.get("mcp_server", ""),
            "mcp_tool": step.action,
            "arguments": context.agent_context.metadata.get("mcp_arguments", {}),
            "execution_trace_id": context.agent_context.metadata.get(
                "execution_trace_id"
            ),
        }

    def _build_payload(
        self, step: TaskStep, context: WorkflowContext
    ) -> dict[str, Any]:
        capability = (step.capabilities[0] if step.capabilities else "").lower()
        if capability == "python":
            return self._python_payload(step, context)
        if capability == "filesystem" or capability == "document":
            return self._filesystem_payload(step, context)
        if capability == "rest":
            return self._rest_payload(step, context)
        if capability == "mcp":
            return self._mcp_payload(step, context)
        return {
            "workspace_root": str(self._workspace_root(context)),
            "execution_trace_id": context.agent_context.metadata.get(
                "execution_trace_id"
            ),
        }

    def execute(
        self, plan: TaskPlan, context: WorkflowContext, trace: ExecutionTrace
    ) -> list[ToolExecutionResult]:
        results: list[ToolExecutionResult] = []
        results_by_tool_name: dict[str, list[dict[str, Any]]] = {}

        trace.metadata.setdefault("tool_results", [])
        with ExecutionTracker(trace).step("Tool Resolution"):
            pass

        for step in plan.steps:
            capability = step.capabilities[0] if step.capabilities else ""
            resolution = self.resolver.resolve(capability)
            if resolution is None:
                result = ToolExecutionResult(
                    tool_name=capability or "unknown",
                    step_id=step.step_id,
                    success=False,
                    stderr=f"No tool resolved for capability: {capability}",
                    duration_ms=0.0,
                    error="unresolved",
                )
            else:
                payload = self._build_payload(step, context)
                result = self.executor.execute(
                    resolution=resolution,
                    context=context.agent_context,
                    payload=payload,
                    step_id=step.step_id,
                )

            results.append(result)
            results_by_tool_name.setdefault(result.tool_name, []).append(
                result.as_metadata()
            )
            trace_step = trace.add_step(
                result.tool_name,
                metadata={
                    "tool": result.tool_name,
                    "step_id": result.step_id,
                    "status": "completed" if result.success else "failed",
                    "duration_ms": result.duration_ms,
                    "stdout_length": len(result.stdout),
                    "generated_files": list(result.artifacts),
                },
            )
            if result.success:
                trace.complete_step(
                    trace_step.id, metadata={"tool_result": result.as_metadata()}
                )
            else:
                trace.fail_step(
                    trace_step.id, metadata={"tool_result": result.as_metadata()}
                )

        context.metadata["tool_results"] = [item.as_metadata() for item in results]
        context.metadata["tool_results_by_tool_name"] = results_by_tool_name
        context.metadata["tool_resolution_count"] = len(results)
        trace.metadata["tool_results"] = [item.as_metadata() for item in results]
        trace.metadata["tool_results_by_tool_name"] = results_by_tool_name
        return results
