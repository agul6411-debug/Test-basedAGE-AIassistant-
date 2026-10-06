"""Tool to type text into the active desktop window.

Security Rule 12:
Log actions (what, when, result) but never log full transcripts
of sensitive text typed by the user.
"""

from typing import Any

from pydantic import BaseModel, Field
from pynput.keyboard import Controller

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class TypeTextSchema(BaseModel):
    """Schema for keyboard text typing."""
    text: str = Field(..., min_length=1, max_length=2000, description="Text to type into active window")


class TypeTextTool(BaseTool):
    """Types characters into the currently focused window."""

    name = "type_text"
    description = "Type given text into the active application window."
    is_dangerous = False
    args_schema = TypeTextSchema

    def __init__(self) -> None:
        self._keyboard = Controller()

    def execute(self, text: str, **kwargs: Any) -> ToolResult:
        if not text:
            return ToolResult(success=False, message="Text cannot be empty.")

        try:
            self._keyboard.type(text)
            return ToolResult(
                success=True,
                message=f"Typed text ({len(text)} characters).",
                data={"char_count": len(text)},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to type text: {e}")


registry.register(TypeTextTool())
