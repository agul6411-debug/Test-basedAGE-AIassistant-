"""Tool to shut down the Windows operating system.

Security Rule 5:
Destructive actions (shutdown, restart, etc.) ALWAYS require confirmation.
"""

from typing import Any

from pydantic import BaseModel

from core.safety.process_runner import SafeProcessRunner
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class ShutdownSchema(BaseModel):
    """Schema for system shutdown (no arguments required)."""


class ShutdownTool(BaseTool):
    """Shuts down the computer after confirmation."""

    name = "shutdown"
    description = "Shut down the computer (requires confirmation)."
    is_dangerous = True
    args_schema = ShutdownSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            # Safe argument list without shell=True
            SafeProcessRunner.run_command(["shutdown", "/s", "/t", "30"])
            return ToolResult(
                success=True,
                message="Computer shutdown initiated with 30-second delay.",
                data={"delay_sec": 30},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to initiate shutdown: {e}")


registry.register(ShutdownTool())
