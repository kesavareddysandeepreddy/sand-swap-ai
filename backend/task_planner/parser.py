"""Deterministic request parser for autonomous task planning."""

from __future__ import annotations

import re

from backend.task_planner.models import TaskGoal


class TaskRequestParser:
    """Parse user requests into structured planning goals without LLM calls."""

    _ACTION_KEYWORDS: tuple[str, ...] = (
        "analyze",
        "archive",
        "build",
        "calculate",
        "call",
        "check",
        "compare",
        "copy",
        "create",
        "delete",
        "execute",
        "extract",
        "fetch",
        "find",
        "generate",
        "index",
        "inspect",
        "list",
        "load",
        "move",
        "parse",
        "read",
        "rename",
        "retrieve",
        "run",
        "save",
        "search",
        "summarize",
        "update",
        "validate",
        "write",
    )

    _TARGET_KEYWORDS: tuple[str, ...] = (
        "api",
        "archive",
        "chat",
        "conversation",
        "database",
        "document",
        "endpoint",
        "file",
        "filesystem",
        "image",
        "memory",
        "metadata",
        "mcp",
        "pipeline",
        "plan",
        "project",
        "python",
        "rag",
        "request",
        "response",
        "rest",
        "step",
        "task",
        "timeline",
        "tool",
        "trace",
        "vision",
        "workflow",
    )

    _CONSTRAINT_PREFIXES: tuple[str, ...] = (
        "do not",
        "without",
        "must",
        "only",
        "never",
    )

    _OUTPUT_PREFIXES: tuple[str, ...] = (
        "return",
        "output",
        "result",
        "produce",
        "respond",
    )

    def parse(self, request: str) -> TaskGoal:
        """Parse the request string into deterministic planning fields."""
        normalized = request.strip()
        segments = self._split_segments(normalized)
        lowered_segments = [segment.lower() for segment in segments]

        actions = sorted(
            {
                token
                for token in self._tokenize(normalized)
                if token in self._ACTION_KEYWORDS
            }
        )
        targets = sorted(
            {
                token
                for token in self._tokenize(normalized)
                if token in self._TARGET_KEYWORDS
            }
        )

        constraints: list[str] = []
        expected_outputs: list[str] = []
        for segment, lowered in zip(segments, lowered_segments, strict=True):
            if any(lowered.startswith(prefix) for prefix in self._CONSTRAINT_PREFIXES):
                constraints.append(segment)
            if any(prefix in lowered for prefix in self._OUTPUT_PREFIXES):
                expected_outputs.append(segment)

        return TaskGoal(
            original_request=normalized,
            actions=actions,
            targets=targets,
            constraints=sorted(set(constraints)),
            expected_outputs=sorted(set(expected_outputs)),
        )

    @staticmethod
    def _split_segments(value: str) -> list[str]:
        segments = [segment.strip() for segment in re.split(r"[\n\.;]+", value)]
        return [segment for segment in segments if segment]

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", value)]
