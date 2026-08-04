"""Validation logic for workflow graph definitions."""

from __future__ import annotations

from collections import defaultdict, deque

from backend.agent_orchestration.domain.workflow import Workflow


class WorkflowValidator:
    """Validates workflow graph structure and references."""

    def validate(
        self, workflow: Workflow, *, known_agent_ids: set[str]
    ) -> dict[str, list[str] | bool]:
        errors: list[str] = []
        warnings: list[str] = []

        node_ids = [node.id for node in workflow.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs are not allowed.")

        edge_ids = [edge.id for edge in workflow.edges]
        if len(edge_ids) != len(set(edge_ids)):
            errors.append("Duplicate edge IDs are not allowed.")

        node_set = set(node_ids)
        if not node_set:
            errors.append("Workflow must contain at least one node.")

        for edge in workflow.edges:
            if edge.source_node_id not in node_set:
                errors.append(f"Broken edge source: {edge.source_node_id}")
            if edge.target_node_id not in node_set:
                errors.append(f"Broken edge target: {edge.target_node_id}")

        start_nodes = [node for node in workflow.nodes if node.node_type == "Start"]
        end_nodes = [node for node in workflow.nodes if node.node_type == "End"]
        if len(start_nodes) != 1:
            errors.append("Workflow must contain exactly one Start node.")
        if len(end_nodes) < 1:
            errors.append("Workflow must contain at least one End node.")

        for node in workflow.nodes:
            if node.node_type == "Agent":
                if not node.agent_id:
                    errors.append(f"Agent node {node.id} is missing agent reference.")
                elif node.agent_id not in known_agent_ids:
                    errors.append(
                        f"Agent node {node.id} references missing agent {node.agent_id}."
                    )

        adjacency: dict[str, list[str]] = defaultdict(list)
        indegree: dict[str, int] = {node_id: 0 for node_id in node_set}
        for edge in workflow.edges:
            adjacency[edge.source_node_id].append(edge.target_node_id)
            indegree[edge.target_node_id] = indegree.get(edge.target_node_id, 0) + 1

        if start_nodes:
            start_id = start_nodes[0].id
            reachable = self._reachable_nodes(start_id, adjacency)
            disconnected = sorted(node_set - reachable)
            if disconnected:
                errors.append("Disconnected nodes detected: " + ", ".join(disconnected))

        if self._has_cycle(node_set, adjacency, indegree):
            errors.append("Cycle detected in workflow graph.")

        for node in workflow.nodes:
            out_count = len(adjacency.get(node.id, []))
            if node.node_type in {"Condition", "Decision"} and out_count < 2:
                errors.append(
                    f"Decision node {node.id} requires at least 2 outgoing edges."
                )
            if node.node_type == "Parallel Split" and out_count < 2:
                errors.append(
                    f"Parallel Split node {node.id} requires at least 2 outgoing edges."
                )
            if node.node_type == "Parallel Join" and out_count > 1:
                errors.append(
                    f"Parallel Join node {node.id} supports only one outgoing edge."
                )
            if node.node_type == "Loop" and out_count < 2:
                errors.append(f"Loop node {node.id} requires loop and exit edges.")
            if node.node_type == "End" and out_count > 0:
                warnings.append(
                    f"End node {node.id} has outgoing edges that will be ignored."
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _reachable_nodes(start_id: str, adjacency: dict[str, list[str]]) -> set[str]:
        queue: deque[str] = deque([start_id])
        seen: set[str] = set()
        while queue:
            node_id = queue.popleft()
            if node_id in seen:
                continue
            seen.add(node_id)
            for target in adjacency.get(node_id, []):
                if target not in seen:
                    queue.append(target)
        return seen

    @staticmethod
    def _has_cycle(
        nodes: set[str],
        adjacency: dict[str, list[str]],
        indegree: dict[str, int],
    ) -> bool:
        queue = deque([node for node in nodes if indegree.get(node, 0) == 0])
        visited = 0
        local_indegree = dict(indegree)
        while queue:
            node = queue.popleft()
            visited += 1
            for target in adjacency.get(node, []):
                local_indegree[target] = local_indegree.get(target, 0) - 1
                if local_indegree[target] == 0:
                    queue.append(target)
        return visited != len(nodes)
