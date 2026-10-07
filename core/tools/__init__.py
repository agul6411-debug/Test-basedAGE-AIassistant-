"""Allowlisted tools and strictly validated action handlers."""

# Import all tool implementations to ensure automatic registration
from core.tools import (
    close_all,
    close_app,
    lock_screen,
    open_app,
    restart,
    restore_layout,
    save_layout,
    set_brightness,
    set_volume,
    shutdown,
    type_text,
    web_search,
    youtube_search,
)
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import ToolRegistry, registry

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "close_all",
    "close_app",
    "lock_screen",
    "open_app",
    "registry",
    "restart",
    "restore_layout",
    "save_layout",
    "set_brightness",
    "set_volume",
    "shutdown",
    "type_text",
    "web_search",
    "youtube_search",
]

