"""WebSocket communication protocol models and schema validation.

Security Rule 3:
All inbound messages from the UI are untrusted and strictly validated with Pydantic.
Never exposes arbitrary shell or file execution.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ==============================================================================
# Inbound Client Messages
# ==============================================================================

class AuthRequest(BaseModel):
    """Client authentication request."""
    type: Literal["auth"] = "auth"
    token: str = Field(min_length=16, max_length=128)


class StartListeningRequest(BaseModel):
    """Client request to start listening for voice input."""
    type: Literal["start_listening"] = "start_listening"


class StopListeningRequest(BaseModel):
    """Client request to stop listening for voice input."""
    type: Literal["stop_listening"] = "stop_listening"


class ExecuteCommandRequest(BaseModel):
    """Client request to execute a typed or voice command."""
    type: Literal["execute_command"] = "execute_command"
    text: str = Field(min_length=1, max_length=1000)
    force_confirmed: bool = False

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Command text cannot be empty.")
        return clean



class ConfirmActionRequest(BaseModel):
    """Client response to a confirmation prompt for dangerous actions."""
    type: Literal["confirm_action"] = "confirm_action"
    action_name: str = Field(min_length=1, max_length=64)
    confirmed: bool


class EmergencyStopRequest(BaseModel):
    """Client instant emergency stop request."""
    type: Literal["emergency_stop"] = "emergency_stop"


class ToggleHandMouseRequest(BaseModel):
    """Client request to start or stop the hand-gesture mouse."""
    type: Literal["toggle_hand_mouse"] = "toggle_hand_mouse"
    enabled: bool


class SaveLayoutRequest(BaseModel):
    """Client request to save current desktop layout."""
    type: Literal["save_layout"] = "save_layout"


class RestoreLayoutRequest(BaseModel):
    """Client request to restore saved desktop layout."""
    type: Literal["restore_layout"] = "restore_layout"


class GetStatusRequest(BaseModel):
    """Client query for overall system status."""
    type: Literal["get_status"] = "get_status"


class GetSettingsRequest(BaseModel):
    """Client query for application settings and allowlist."""
    type: Literal["get_settings"] = "get_settings"


class UpdateSettingRequest(BaseModel):
    """Client request to update specific safe configuration setting."""
    type: Literal["update_setting"] = "update_setting"
    key: str = Field(min_length=1, max_length=64)
    value: Any


# Type union of all permitted incoming requests
ClientMessage = (
    AuthRequest
    | StartListeningRequest
    | StopListeningRequest
    | ExecuteCommandRequest
    | ConfirmActionRequest
    | EmergencyStopRequest
    | ToggleHandMouseRequest
    | SaveLayoutRequest
    | RestoreLayoutRequest
    | GetStatusRequest
    | GetSettingsRequest
    | UpdateSettingRequest
)


def parse_client_message(data: dict[str, Any]) -> ClientMessage:
    """Parse and strictly validate an incoming client JSON payload.

    Args:
        data: Parsed JSON dictionary.

    Returns:
        Validated ClientMessage instance.

    Raises:
        ValueError: If message type is missing or invalid.
        pydantic.ValidationError: If payload violates schema.
    """
    msg_type = data.get("type")
    type_map: dict[str, type[BaseModel]] = {
        "auth": AuthRequest,
        "start_listening": StartListeningRequest,
        "stop_listening": StopListeningRequest,
        "execute_command": ExecuteCommandRequest,
        "confirm_action": ConfirmActionRequest,
        "emergency_stop": EmergencyStopRequest,
        "toggle_hand_mouse": ToggleHandMouseRequest,
        "save_layout": SaveLayoutRequest,
        "restore_layout": RestoreLayoutRequest,
        "get_status": GetStatusRequest,
        "get_settings": GetSettingsRequest,
        "update_setting": UpdateSettingRequest,
    }

    schema = type_map.get(str(msg_type))
    if not schema:
        raise ValueError(f"Unknown or unsupported message type: '{msg_type}'")

    return schema.model_validate(data)  # type: ignore[return-value]


# ==============================================================================
# Outbound Server Messages / Events
# ==============================================================================

class ServerEvent(BaseModel):
    """Base class for all outbound server messages."""
    type: str
    timestamp: str = ""


class AuthResultEvent(ServerEvent):
    """Outbound authentication status event."""
    type: Literal["auth_result"] = "auth_result"
    success: bool
    message: str


class StateChangeEvent(ServerEvent):
    """Voice assistant activity state: idle, listening, thinking, speaking."""
    type: Literal["state_change"] = "state_change"
    state: Literal["idle", "listening", "thinking", "speaking"]


class StatusUpdateEvent(ServerEvent):
    """Comprehensive system status update."""
    type: Literal["status_update"] = "status_update"
    mic_active: bool = False
    camera_active: bool = False
    hand_mouse_active: bool = False
    offline_mode: bool = True
    core_running: bool = True
    active_state: str = "idle"
    recent_commands: list[dict[str, Any]] = Field(default_factory=list)
    models: dict[str, str] = Field(default_factory=dict)
    layout_snapshots_count: int = 0


class CommandResultEvent(ServerEvent):
    """Result of command execution dispatch."""
    type: Literal["command_result"] = "command_result"
    matched: bool
    success: bool
    message: str
    tool_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ConfirmationRequiredEvent(ServerEvent):
    """Triggered when a dangerous action requires explicit user approval."""
    type: Literal["confirmation_required"] = "confirmation_required"
    action_name: str
    prompt: str
    timeout_sec: float = 10.0


class EmergencyStopEvent(ServerEvent):
    """Notifies client that emergency stop has been engaged."""
    type: Literal["emergency_stop_triggered"] = "emergency_stop_triggered"
    message: str = "Emergency stop activated. All hardware and actions halted."


class ErrorEvent(ServerEvent):
    """Error notification for invalid operations or errors."""
    type: Literal["error"] = "error"
    message: str
    code: str = "GENERIC_ERROR"
