"""Tool to adjust display brightness."""

from typing import Any

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class SetBrightnessSchema(BaseModel):
    """Schema for screen brightness adjustments."""
    level: int | None = Field(None, ge=0, le=100, description="Absolute brightness percentage (0-100)")
    delta: int | None = Field(None, ge=-100, le=100, description="Brightness change amount (+10 or -10)")


class SetBrightnessTool(BaseTool):
    """Controls display screen brightness."""

    name = "set_brightness"
    description = "Adjust screen display brightness (0-100)."
    is_dangerous = False
    args_schema = SetBrightnessSchema

    def execute(
        self,
        level: int | None = None,
        delta: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            import screen_brightness_control as sbc

            current_list = sbc.get_brightness()
            current = int(current_list[0]) if current_list else 50

            if level is not None:
                new_level = max(0, min(100, level))
                sbc.set_brightness(new_level)
                return ToolResult(
                    success=True,
                    message=f"Brightness set to {new_level}%.",
                    data={"brightness": new_level},
                )

            if delta is not None:
                new_level = max(0, min(100, current + delta))
                sbc.set_brightness(new_level)
                action = "increased" if delta > 0 else "decreased"
                return ToolResult(
                    success=True,
                    message=f"Brightness {action} to {new_level}%.",
                    data={"brightness": new_level},
                )

            return ToolResult(
                success=True,
                message=f"Current brightness is {current}%.",
                data={"brightness": current},
            )

        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to adjust brightness: {e}")


registry.register(SetBrightnessTool())
