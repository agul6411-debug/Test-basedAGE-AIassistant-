"""Tool to control Windows system volume using pycaw."""

from typing import Any

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class SetVolumeSchema(BaseModel):
    """Schema for volume adjustments."""
    level: int | None = Field(None, ge=0, le=100, description="Absolute volume level (0-100)")
    delta: int | None = Field(None, ge=-100, le=100, description="Volume change amount (+10 or -10)")
    mute: bool | None = Field(None, description="Set mute state (True/False)")


class SetVolumeTool(BaseTool):
    """Controls master system audio volume."""

    name = "set_volume"
    description = "Adjust or mute master audio volume (0-100)."
    is_dangerous = False
    args_schema = SetVolumeSchema

    def execute(
        self,
        level: int | None = None,
        delta: int | None = None,
        mute: bool | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            if not speakers or not hasattr(speakers, "EndpointVolume"):
                return ToolResult(success=False, message="No active audio output device found.")

            endpoint = speakers.EndpointVolume

            # 1. Handle Mute
            if mute is not None:
                endpoint.SetMute(1 if mute else 0, None)
                state = "muted" if mute else "unmuted"
                return ToolResult(success=True, message=f"Audio {state}.", data={"muted": mute})

            current_scalar = endpoint.GetMasterVolumeLevelScalar()
            current_pct = round(current_scalar * 100)

            # 2. Handle Absolute Level
            if level is not None:
                new_scalar = max(0.0, min(1.0, level / 100.0))
                endpoint.SetMasterVolumeLevelScalar(new_scalar, None)
                endpoint.SetMute(0, None)  # Unmute if volume is explicitly set
                return ToolResult(
                    success=True,
                    message=f"Volume set to {level}%.",
                    data={"volume": level},
                )

            # 3. Handle Delta (volume up / down)
            if delta is not None:
                new_pct = max(0, min(100, current_pct + delta))
                new_scalar = new_pct / 100.0
                endpoint.SetMasterVolumeLevelScalar(new_scalar, None)
                endpoint.SetMute(0, None)
                action = "increased" if delta > 0 else "decreased"
                return ToolResult(
                    success=True,
                    message=f"Volume {action} to {new_pct}%.",
                    data={"volume": new_pct},
                )

            return ToolResult(
                success=True,
                message=f"Current volume is {current_pct}%.",
                data={"volume": current_pct},
            )

        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to adjust volume: {e}")


registry.register(SetVolumeTool())
