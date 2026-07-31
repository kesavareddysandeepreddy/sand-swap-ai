from __future__ import annotations

from backend.tool_sdk import BaseTool, ToolRegistry, default_tool_registry, tool
from backend.tool_sdk.context import ToolContext
from backend.tools.capability_registry import CapabilityRegistry


@tool(
    name="DecoratedExampleTool",
    description="Example decorated tool",
    capabilities=["example", "demo"],
    priority=110,
)
class _DecoratedExampleTool(BaseTool):
    def name(self) -> str:
        return "DecoratedExampleTool"

    def description(self) -> str:
        return "Example decorated tool"

    def capabilities(self) -> list[str]:
        return ["example", "demo"]

    def execute(self, context: ToolContext | dict[str, object]) -> str:
        _ = context
        return "Not Implemented"


def test_decorator_auto_registration_default_registry() -> None:
    tool_class = default_tool_registry.get("DecoratedExampleTool")

    assert tool_class is _DecoratedExampleTool


def test_registry_lookup_and_capability_find() -> None:
    registry = ToolRegistry()
    registry.register(_DecoratedExampleTool)

    assert registry.get("DecoratedExampleTool") is _DecoratedExampleTool
    matches = registry.find_by_capability("example")
    assert matches and matches[0] is _DecoratedExampleTool


def test_bridge_to_capability_registry() -> None:
    capability_registry = CapabilityRegistry()
    registry = ToolRegistry(capability_registry=capability_registry)

    registry.register(_DecoratedExampleTool)

    metadata = capability_registry.get_tool("DecoratedExampleTool")
    assert metadata is not None
    assert metadata.capabilities == ["example", "demo"]


def test_placeholder_tool_discovery() -> None:
    from backend.tools.filesystem_tool import FilesystemTool
    from backend.tools.python_tool import PythonTool
    from backend.tools.rest_tool import RESTTool

    registry = ToolRegistry()
    registry.register(FilesystemTool)
    registry.register(PythonTool)
    registry.register(RESTTool)

    tools = registry.list()
    names = [tool_class.__name__ for tool_class in tools]

    assert "FilesystemTool" in names
    assert "PythonTool" in names
    assert "RESTTool" in names

    fs = FilesystemTool()
    py = PythonTool()
    rest = RESTTool()

    fs_result = fs.execute({})
    assert fs_result["success"] is False
    assert fs_result["operation"] == ""
    assert "Unsupported operation" in fs_result["error"]
    py_result = py.execute({})
    assert py_result["success"] is False
    assert isinstance(py_result["stdout"], str)
    assert isinstance(py_result["stderr"], str)
    assert isinstance(py_result["generated_files"], list)
    assert isinstance(py_result["execution_time"], float)
    rest_result = rest.execute({})
    assert rest_result["success"] is False
    assert "url is required" in rest_result["stderr"]
