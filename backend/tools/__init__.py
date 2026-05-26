"""Tools module for agent capabilities"""

from typing import Dict, Any, Callable, Optional


class Tool:
    """Base tool class"""
    
    def __init__(self, name: str, description: str, func: Callable):
        """Initialize tool"""
        self.name = name
        self.description = description
        self.func = func
    
    async def execute(self, **kwargs) -> Any:
        """Execute tool"""
        return await self.func(**kwargs) if hasattr(self.func, '__await__') else self.func(**kwargs)


class ToolRegistry:
    """Registry for managing tools"""
    
    def __init__(self):
        """Initialize tool registry"""
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self.tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> Dict[str, str]:
        """List all registered tools with descriptions"""
        return {name: tool.description for name, tool in self.tools.items()}


# Global tool registry
_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry"""
    return _tool_registry


__all__ = ["Tool", "ToolRegistry", "get_tool_registry"]
