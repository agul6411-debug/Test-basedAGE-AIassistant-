"""Tool to close an allowlisted application.

Security Rule 4:
Only processes matching an allowlisted app in config.yaml can be closed.
"""

from typing import Any

import psutil
from pydantic import BaseModel, Field

from core.config import load_config
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class CloseAppSchema(BaseModel):
    """Schema for closing an application."""
    app_name: str = Field(description="Name or alias of the application from the allowlist")


class CloseAppTool(BaseTool):
    """Closes running processes matching an allowlisted app."""

    name = "close_app"
    description = "Close running instances of an allowlisted application."
    is_dangerous = False
    args_schema = CloseAppSchema

    def execute(self, app_name: str, **kwargs: Any) -> ToolResult:
        config = load_config()
        clean_name = app_name.strip().lower()

        if clean_name not in config.safety.app_allowlist:
            allowed = ", ".join(config.safety.app_allowlist.keys())
            return ToolResult(
                success=False,
                message=f"Application '{app_name}' is not in the allowlist. Allowed: {allowed}",
            )

        target_exe = config.safety.app_allowlist[clean_name].lower()
        closed_count = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname == target_exe or pname == f"{target_exe}.exe":
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if closed_count > 0:
            return ToolResult(
                success=True,
                message=f"Closed {closed_count} instance(s) of {clean_name}.",
                data={"closed_count": closed_count},
            )

        return ToolResult(
            success=True,
            message=f"No running instances of {clean_name} found.",
            data={"closed_count": 0},
        )


registry.register(CloseAppTool())
