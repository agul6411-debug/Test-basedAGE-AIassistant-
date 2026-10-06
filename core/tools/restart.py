"""Tool to restart the Windows operating system.

Security Rule 5:
Destructive actions (restart, shutdown, etc.) ALWAYS require confirmation.
"""

from typing import Any

from pydantic import BaseModel

from core.safety.process_runner import SafeProcessRunner
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class RestartSchema(BaseModel):
    """Schema for system restart (no arguments required)."""


class RestartTool(BaseTool):
    """Restarts the computer after confirmation."""

    name = "restart"
    description = "Restart the computer (requires confirmation)."
    is_dangerous = True
    args_schema = RestartSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            SafeProcessRunner.run_command(["shutdown", "/r", "/t", "30"])
            return ToolResult(
                success=True,
                message="Computer restart initiated with 30-second delay.",
                data={"delay_sec": 30},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to initiate restart: {e}")


registry.register(RestartTool())
