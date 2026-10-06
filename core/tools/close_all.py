"""Tool to close all open application windows.

Security Rule 5:
Destructive actions (close-all, etc.) ALWAYS require confirmation.
"""

from typing import Any

import psutil
from pydantic import BaseModel

from core.config import load_config
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class CloseAllSchema(BaseModel):
    """Schema for close all open applications."""


class CloseAllTool(BaseTool):
    """Closes all active allowlisted application windows."""

    name = "close_all"
    description = "Close all running instances of allowlisted applications (requires confirmation)."
    is_dangerous = True
    args_schema = CloseAllSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        config = load_config()
        allowed_exes = {exe.lower() for exe in config.safety.app_allowlist.values()}

        closed_count = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in allowed_exes:
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return ToolResult(
            success=True,
            message=f"Closed {closed_count} running application window(s).",
            data={"closed_count": closed_count},
        )


registry.register(CloseAllTool())
