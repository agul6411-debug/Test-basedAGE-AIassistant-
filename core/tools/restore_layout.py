"""Tool to restore desktop layout from SQLite snapshot.

Security Rule 4: Relaunches ONLY allowlisted apps from config.yaml.
Security Rule 5: Requires spoken or button confirmation.
Security Invariant: Never kills or modifies existing processes, never touches user files.
"""

from typing import Any

from pydantic import BaseModel

from core.layout.db import LayoutDB
from core.layout.icon_manager import DesktopIconManager
from core.layout.window_manager import WindowManager
from core.logger import get_logger
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry

logger = get_logger("tools.restore_layout")


class RestoreLayoutSchema(BaseModel):
    """Schema for restoring desktop layout snapshot."""


class RestoreLayoutTool(BaseTool):
    """Restores open windows and desktop icon positions from the latest snapshot."""

    name = "restore_layout"
    description = "Restore desktop window positions and icon layout from the latest snapshot (requires confirmation)."
    is_dangerous = True
    args_schema = RestoreLayoutSchema

    def execute(self, **kwargs: Any) -> ToolResult:
        """Relaunch missing allowlisted apps, position windows, and restore icon coordinates."""
        try:
            db = LayoutDB()
            latest = db.get_latest_snapshot()
            if not latest:
                return ToolResult(
                    success=False,
                    message="No desktop layout snapshot found to restore.",
                    data={},
                )

            windows = latest.get("windows", [])
            icons = latest.get("icons", [])

            # 1. Relaunch missing allowlisted apps and reposition windows
            win_mgr = WindowManager()
            win_summary = win_mgr.restore_windows(windows)

            # 2. Restore desktop icons via ListView
            icon_mgr = DesktopIconManager()
            icon_success = icon_mgr.restore_icon_positions(icons)

            msg_parts = [
                f"Restored layout from snapshot #{latest['id']}.",
                f"Windows positioned: {win_summary['windows_positioned']}/{win_summary['total_saved_windows']}.",
            ]
            if win_summary["relaunched_apps"]:
                msg_parts.append(f"Relaunched apps: {', '.join(win_summary['relaunched_apps'])}.")
            if icons:
                icon_status = "sent" if icon_success else "failed"
                msg_parts.append(f"Desktop icon restore: {icon_status} ({len(icons)} icons).")

            return ToolResult(
                success=True,
                message=" ".join(msg_parts),
                data={
                    "snapshot_id": latest["id"],
                    "windows": win_summary,
                    "icon_success": icon_success,
                    "icon_count": len(icons),
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to restore layout: %s", e)
            return ToolResult(
                success=False,
                message=f"Failed to restore desktop layout: {e}",
                data={},
            )


registry.register(RestoreLayoutTool())
