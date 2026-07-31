from __future__ import annotations

from backend.tools.capability_registry import CapabilityRegistry
from backend.tools.tool_metadata import ToolMetadata


def test_tool_registration_and_get() -> None:
    registry = CapabilityRegistry()
    metadata = ToolMetadata(
        name="ToolA",
        description="A tool",
        capabilities=["search"],
        supported_inputs=["text"],
        supported_outputs=["result"],
        permissions=["read"],
        priority=1,
    )

    registry.register_tool(metadata)

    assert registry.get_tool("ToolA") == metadata
    assert [item.name for item in registry.list_tools()] == ["ToolA"]


def test_capability_lookup_and_priority_ordering() -> None:
    registry = CapabilityRegistry()
    registry.register_tool(
        ToolMetadata(
            name="B",
            description="",
            capabilities=["memory"],
            priority=10,
        )
    )
    registry.register_tool(
        ToolMetadata(
            name="A",
            description="",
            capabilities=["memory"],
            priority=10,
        )
    )
    registry.register_tool(
        ToolMetadata(
            name="C",
            description="",
            capabilities=["memory"],
            priority=20,
        )
    )

    matches = registry.find_by_capability("memory")

    assert [item.name for item in matches] == ["C", "A", "B"]


def test_unknown_capability_returns_empty() -> None:
    registry = CapabilityRegistry()
    registry.register_tool(
        ToolMetadata(
            name="ToolA",
            description="",
            capabilities=["search"],
        )
    )

    assert registry.find_by_capability("nonexistent") == []


def test_unregister_tool() -> None:
    registry = CapabilityRegistry()
    registry.register_tool(
        ToolMetadata(
            name="ToolA",
            description="",
            capabilities=["search"],
        )
    )

    registry.unregister_tool("ToolA")

    assert registry.get_tool("ToolA") is None
