"""Tool registry for discovering and dispatching tools."""


from core.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: BaseTool subclass instance.
        """
        if not tool.name:
            raise ValueError("Tool name cannot be empty.")
        self._tools[tool.name.lower()] = tool

    def get(self, name: str) -> BaseTool | None:
        """Look up tool by name."""
        return self._tools.get(name.lower())

    def list_tools(self) -> list[BaseTool]:
        """Return list of all registered tools."""
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._tools


# Global registry instance
registry = ToolRegistry()
