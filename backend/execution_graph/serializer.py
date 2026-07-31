"""Execution graph serialization utilities."""

from __future__ import annotations

from typing import Any

from backend.execution_graph.models import ExecutionGraph


class ExecutionGraphSerializer:
    """Serialize execution graph structures for metadata transport."""

    @staticmethod
    def to_metadata(graph: ExecutionGraph) -> dict[str, Any]:
        """Serialize an execution graph into deterministic metadata."""
        return graph.as_metadata()
