"""Tool to save the current desktop window and icon layout.

Security Rule 13: Layout data is stored in SQLite strictly within data/.
"""

from typing import Any

from pydantic import BaseModel

from core.layout.autosave import LayoutAutoSaver
from core.logger import get_logger
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry

logger = get_logger("tools.save_layout")


class SaveLayoutSchema(BaseModel):
    """Schema for saving desktop layout snapshot."""


class SaveLayoutTool(BaseTool):
    """Saves current desktop open window positions and icon layout."""

    name = "save_layout"
    description = "Save current desktop window positions and icon layout to database."
    is_dangerous = False
    args_schema = SaveLayoutSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        """Capture and save the desktop layout."""
        try:
            auto_saver = LayoutAutoSaver()
            snapshot_id = auto_saver.capture_and_save(trigger_type="manual")
            if snapshot_id > 0:
                return ToolResult(
                    success=True,
                    message=f"Desktop layout saved successfully (Snapshot #{snapshot_id}).",
                    data={"snapshot_id": snapshot_id},
                )
            return ToolResult(
                success=False,
                message="Failed to save desktop layout.",
                data={},
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to save layout: %s", e)
            return ToolResult(
                success=False,
                message=f"Failed to save desktop layout: {e}",
                data={},
            )


registry.register(SaveLayoutTool())
