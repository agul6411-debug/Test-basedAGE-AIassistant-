"""Tool to lock the Windows workstation."""

import ctypes
from typing import Any

from pydantic import BaseModel

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class LockScreenSchema(BaseModel):
    """Schema for locking workstation (no arguments required)."""


class LockScreenTool(BaseTool):
    """Locks the current Windows workstation."""

    name = "lock_screen"
    description = "Lock the Windows desktop session."
    is_dangerous = False
    args_schema = LockScreenSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            # Native Windows user32 API LockWorkStation
            result = ctypes.windll.user32.LockWorkStation()
            if result != 0:
                return ToolResult(success=True, message="Workstation locked successfully.")
            return ToolResult(success=False, message="Failed to lock workstation via user32.")
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Lock screen error: {e}")


registry.register(LockScreenTool())
