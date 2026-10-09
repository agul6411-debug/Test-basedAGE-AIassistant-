"""Tool to close an allowlisted application.

Security Rule 4:
Only processes matching an allowlisted app in config.yaml can be closed.
"""

from pathlib import Path
from typing import Any

import psutil
from pydantic import BaseModel, Field

from core.config import load_config
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry

APP_ALIASES: dict[str, str] = {
    "calculator": "calc",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "google chrome": "chrome",
    "google": "chrome",
    "browser": "chrome",
    "microsoft edge": "edge",
    "file explorer": "explorer",
    "files": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "word": "word",
    "ms word": "word",
    "microsoft word": "word",
    "excel": "excel",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "ms powerpoint": "powerpoint",
    "slides": "powerpoint",
    "paint": "paint",
    "ms paint": "paint",
    "onenote": "onenote",
    "outlook": "outlook",
    "mail": "outlook",
    "email": "outlook",
    "access": "access",
    "ms access": "access",
    "task manager": "taskmanager",
    "tasks": "taskmanager",
    "control panel": "controlpanel",
    "settings": "controlpanel",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "screenshot": "snippingtool",
    "media player": "media",
    "music": "media",
    "player": "media",
}


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
        clean_name = APP_ALIASES.get(clean_name, clean_name)

        if clean_name not in config.safety.app_allowlist:
            allowed = ", ".join(config.safety.app_allowlist.keys())
            return ToolResult(
                success=False,
                message=f"Application '{app_name}' is not in the allowlist. Allowed: {allowed}",
            )

        raw_exe = config.safety.app_allowlist[clean_name]
        target_path = Path(raw_exe)
        target_name = target_path.name.lower()
        target_stem = target_path.stem.lower()
        allowed_names = {target_name, f"{target_stem}.exe", target_stem}

        closed_count = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in allowed_names:
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
