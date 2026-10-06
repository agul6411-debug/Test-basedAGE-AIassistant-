"""Tool to open an allowlisted application.

Security Rule 4:
Apps can only be launched from an allowlist in config.yaml,
never from arbitrary strings.
"""

from typing import Any

from pydantic import BaseModel, Field

from core.config import load_config
from core.safety.process_runner import ProcessSecurityError, SafeProcessRunner
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class OpenAppSchema(BaseModel):
    """Schema for opening an application."""
    app_name: str = Field(description="Name or alias of the application from the allowlist")


class OpenAppTool(BaseTool):
    """Launches an application strictly from the config allowlist."""

    name = "open_app"
    description = "Open an approved desktop application from the allowlist."
    is_dangerous = False
    args_schema = OpenAppSchema

    def execute(self, app_name: str, **kwargs: Any) -> ToolResult:
        config = load_config()
        clean_name = app_name.strip().lower()

        if clean_name not in config.safety.app_allowlist:
            allowed = ", ".join(config.safety.app_allowlist.keys())
            return ToolResult(
                success=False,
                message=f"Application '{app_name}' is not permitted. Allowed applications: {allowed}",
            )

        try:
            SafeProcessRunner.launch_allowlisted_app(clean_name, config.safety.app_allowlist)
            return ToolResult(
                success=True,
                message=f"Opened {clean_name}.",
                data={"app": clean_name},
            )
        except ProcessSecurityError as e:
            return ToolResult(success=False, message=str(e))


registry.register(OpenAppTool())
