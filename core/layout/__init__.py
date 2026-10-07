"""Desktop layout manager and autostart package."""

from core.layout.autosave import LayoutAutoSaver
from core.layout.autostart import AutostartManager
from core.layout.db import LayoutDB
from core.layout.icon_manager import DesktopIconManager
from core.layout.window_manager import WindowManager

__all__ = [
    "AutostartManager",
    "DesktopIconManager",
    "LayoutAutoSaver",
    "LayoutDB",
    "WindowManager",
]
