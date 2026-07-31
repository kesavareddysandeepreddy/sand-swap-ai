"""In-memory capability registry for tool metadata."""

from __future__ import annotations

from backend.tools.tool_metadata import ToolMetadata


class CapabilityRegistry:
    """Register and resolve tools by declared capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}

    def register_tool(self, metadata: ToolMetadata) -> None:
        """Register or replace a tool metadata entry."""
        self._tools[metadata.name] = metadata

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool metadata entry by name."""
        self._tools.pop(name, None)

    def list_tools(self) -> list[ToolMetadata]:
        """List all tool metadata entries."""
        return [self._tools[name] for name in sorted(self._tools.keys())]

    def find_by_capability(self, capability: str) -> list[ToolMetadata]:
        """Return tools supporting the requested capability.

        Ordering is deterministic: highest priority first, then name.
        """
        normalized = capability.strip().lower()
        if not normalized:
            return []

        matches = [
            metadata
            for metadata in self._tools.values()
            if normalized in [item.lower() for item in metadata.capabilities]
        ]
        return sorted(matches, key=lambda item: (-item.priority, item.name))

    def get_tool(self, name: str) -> ToolMetadata | None:
        """Resolve a tool by name."""
        return self._tools.get(name)


DEFAULT_TOOL_METADATA: tuple[ToolMetadata, ...] = (
    ToolMetadata(
        name="KnowledgeService",
        description="Knowledge retrieval and search tool",
        capabilities=["knowledge", "search", "documents"],
        supported_inputs=["text", "query"],
        supported_outputs=["knowledge_context", "matches"],
        permissions=["knowledge:read"],
        priority=90,
    ),
    ToolMetadata(
        name="VisionProvider",
        description="Vision analysis tool",
        capabilities=["image", "vision", "ocr"],
        supported_inputs=["image", "attachment"],
        supported_outputs=["vision_context", "analysis"],
        permissions=["vision:read"],
        priority=80,
    ),
    ToolMetadata(
        name="Memory",
        description="Memory recall tool",
        capabilities=["memory", "recall"],
        supported_inputs=["text", "query"],
        supported_outputs=["memory_context"],
        permissions=["memory:read"],
        priority=85,
    ),
    ToolMetadata(
        name="RAG",
        description="Retrieval-augmented generation tool",
        capabilities=["rag", "retrieval"],
        supported_inputs=["text", "query"],
        supported_outputs=["retrieved_chunks"],
        permissions=["documents:read"],
        priority=88,
    ),
    ToolMetadata(
        name="MCP",
        description="Model Context Protocol external automation tool",
        capabilities=["external", "automation", "mcp"],
        supported_inputs=["tool_call", "resource_uri"],
        supported_outputs=["tool_result", "resource_content"],
        permissions=["mcp:invoke"],
        priority=70,
    ),
    ToolMetadata(
        name="WorkflowEngine",
        description="Workflow orchestration tool",
        capabilities=["workflow", "orchestration"],
        supported_inputs=["workflow"],
        supported_outputs=["workflow_result"],
        permissions=["workflow:execute"],
        priority=95,
    ),
    ToolMetadata(
        name="FilesystemTool",
        description="Filesystem placeholder tool metadata",
        capabilities=["filesystem"],
        supported_inputs=["path"],
        supported_outputs=["file_content"],
        permissions=["filesystem:read"],
        priority=40,
    ),
)


def register_default_tool_metadata(registry: CapabilityRegistry) -> None:
    """Register baseline platform tool metadata entries."""
    for metadata in DEFAULT_TOOL_METADATA:
        registry.register_tool(metadata)
