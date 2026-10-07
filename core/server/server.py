"""Secure Local WebSocket Server for Flutter Desktop UI.

Security Rule 1: Binds to 127.0.0.1 ONLY, never 0.0.0.0.
Security Rule 1: Require random per-session auth token and check Origin.
Security Rule 2: Subprocess argument lists without shell=True.
Security Rule 3: Validates every message against strict Pydantic schemas.
Security Rule 5: Destructive actions require confirmation.
Security Rule 10: Immediate emergency-stop handler.
"""

import asyncio
import json
import time
import urllib.parse
from datetime import datetime, timezone

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from core.brain.router import CommandRouter
from core.config import AppConfig, load_config
from core.hand_mouse_controller import HandMouseController
from core.layout.autosave import LayoutAutoSaver
from core.layout.db import LayoutDB
from core.logger import get_logger
from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.safety.emergency_stop import EmergencyStop
from core.safety.token_manager import SessionTokenManager, get_default_token_manager
from core.server.protocol import (
    AuthResultEvent,
    ClientMessage,
    CommandResultEvent,
    ConfirmationRequiredEvent,
    EmergencyStopEvent,
    ErrorEvent,
    ExecuteCommandRequest,
    ServerEvent,
    StateChangeEvent,
    StatusUpdateEvent,
    ToggleHandMouseRequest,
    parse_client_message,
)
from core.tools.registry import registry

logger = get_logger("server.core")

# Close code for unauthorized access (RFC 6455 private range 4000-4999)
CLOSE_CODE_UNAUTHORIZED = 4401
CLOSE_CODE_FORBIDDEN = 4403
AUTH_TIMEOUT_SECONDS = 5.0
MAX_REQUESTS_PER_MINUTE = 30


class AGEServer:
    """Secure local WebSocket server bridging Core engine with Flutter Desktop UI."""

    def __init__(
        self,
        config: AppConfig | None = None,
        router: CommandRouter | None = None,
        hand_mouse: HandMouseController | None = None,
        token_mgr: SessionTokenManager | None = None,
    ) -> None:
        self.config = config or load_config()

        # Security Rule 1: Verify loopback binding
        host = self.config.server.host.strip().lower()
        if host in ("0.0.0.0", "::", "all"):  # nosec: B104
            raise ValueError("SECURITY VIOLATION: Server host must be 127.0.0.1, never 0.0.0.0")
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"SECURITY VIOLATION: Server host must be loopback, got '{host}'")

        self.host = host
        self.port = self.config.server.port
        self.allowed_origins = [o.lower() for o in self.config.server.allowed_origins]

        self.token_mgr = token_mgr or get_default_token_manager()
        # Ensure session token is initialized
        try:
            self.expected_token = self.token_mgr.read_token()
        except Exception:  # noqa: BLE001
            self.expected_token = self.token_mgr.generate_token()


        self.emergency_mgr = EmergencyStop()
        self.confirmation_mgr = ConfirmationManager()
        self.action_logger = ActionLogger()
        self.router = router or CommandRouter(
            confirmation_manager=self.confirmation_mgr,
            action_logger=self.action_logger,
        )
        self.hand_mouse = hand_mouse or HandMouseController()
        self.auto_saver = LayoutAutoSaver()

        self._active_connections: set[ServerConnection] = set()
        self._authenticated_connections: set[ServerConnection] = set()
        self._rate_limits: dict[ServerConnection, list[float]] = {}
        self._current_state: str = "idle"  # idle, listening, thinking, speaking
        self._server: Server | None = None
        self._pending_confirmations: dict[str, asyncio.Future[bool]] = {}

    @property
    def current_state(self) -> str:
        return self._current_state

    def set_state(self, new_state: str) -> None:
        """Update and broadcast voice state: idle, listening, thinking, speaking."""
        if new_state in ("idle", "listening", "thinking", "speaking"):
            self._current_state = new_state
            asyncio.create_task(
                self.broadcast_event(
                    StateChangeEvent(
                        type="state_change",
                        state=new_state,  # type: ignore[arg-type]
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
            )

    def _check_origin(self, origin: str | None) -> bool:
        """Validate client Origin header against allowed list and local addresses."""
        if not origin:
            # Native desktop Windows client often sends no Origin header
            return True

        clean = origin.strip().lower()
        if clean in self.allowed_origins:
            return True

        # Allow local loopback origins with arbitrary ports (e.g. Flutter web dev / tests)
        parsed = urllib.parse.urlparse(clean)
        if parsed.hostname in ("127.0.0.1", "localhost"):
            return True

        logger.warning("Rejected connection with unauthorized Origin: %s", origin)
        return False

    def _check_rate_limit(self, websocket: ServerConnection) -> bool:
        """Check if connection exceeded MAX_REQUESTS_PER_MINUTE."""
        now = time.monotonic()
        history = self._rate_limits.setdefault(websocket, [])
        # Retain timestamps within the last 60 seconds
        history = [t for t in history if now - t < 60.0]
        self._rate_limits[websocket] = history

        if len(history) >= MAX_REQUESTS_PER_MINUTE:
            logger.warning("Connection rate limit exceeded (%d requests in 60s).", len(history))
            return False

        history.append(now)
        return True

    async def broadcast_event(self, event: ServerEvent) -> None:
        """Send event payload to all authenticated connected clients."""
        if not self._authenticated_connections:
            return

        payload = event.model_dump_json()
        dead = []
        for ws in self._authenticated_connections:
            try:
                await ws.send(payload)
            except (ConnectionClosed, Exception):  # noqa: BLE001
                dead.append(ws)


        for ws in dead:
            self._authenticated_connections.discard(ws)
            self._active_connections.discard(ws)

    async def handle_connection(self, websocket: ServerConnection) -> None:
        """Connection handler lifecycle for each incoming WebSocket client."""
        # 1. Origin verification
        origin = websocket.request.headers.get("Origin") if websocket.request else None
        if not self._check_origin(origin):
            logger.warning("Connection rejected due to invalid origin '%s'", origin)
            await websocket.close(code=CLOSE_CODE_FORBIDDEN, reason="Forbidden origin")
            return

        self._active_connections.add(websocket)
        logger.info("New client connection established from %s (Origin: %s)", websocket.remote_address, origin)

        try:
            # 2. Enforce initial authentication within AUTH_TIMEOUT_SECONDS
            auth_msg_raw = await asyncio.wait_for(websocket.recv(), timeout=AUTH_TIMEOUT_SECONDS)
            auth_data = json.loads(auth_msg_raw) if isinstance(auth_msg_raw, str) else {}
            token = auth_data.get("token", "")

            # Security Rule 1: Constant-time token verification
            if not SessionTokenManager.verify_token(token, self.expected_token):
                logger.warning("Authentication failed: invalid session token from %s", websocket.remote_address)
                await websocket.send(
                    AuthResultEvent(
                        type="auth_result",
                        success=False,
                        message="Invalid session authentication token.",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ).model_dump_json()
                )
                await websocket.close(code=CLOSE_CODE_UNAUTHORIZED, reason="Invalid token")
                return

            self._authenticated_connections.add(websocket)
            logger.info("Client authenticated successfully: %s", websocket.remote_address)
            await websocket.send(
                AuthResultEvent(
                    type="auth_result",
                    success=True,
                    message="Authenticated successfully.",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ).model_dump_json()
            )

            # Send initial system status
            await self._send_status(websocket)

            # 3. Message processing loop
            async for raw_message in websocket:
                if not self._check_rate_limit(websocket):
                    await websocket.send(
                        ErrorEvent(
                            type="error",
                            message="Rate limit exceeded. Maximum 30 requests per minute.",
                            code="RATE_LIMIT_EXCEEDED",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        ).model_dump_json()
                    )
                    continue

                await self._process_message(websocket, raw_message)

        except asyncio.TimeoutError:
            logger.warning("Client timed out waiting for auth message (%s)", websocket.remote_address)
            await websocket.close(code=CLOSE_CODE_UNAUTHORIZED, reason="Auth timeout")
        except ConnectionClosed:
            logger.info("Client disconnected: %s", websocket.remote_address)
        except Exception as e:  # noqa: BLE001
            logger.error("Error in connection handler: %s", e)
        finally:
            self._authenticated_connections.discard(websocket)
            self._active_connections.discard(websocket)
            self._rate_limits.pop(websocket, None)

    async def _process_message(self, websocket: ServerConnection, raw_message: str | bytes) -> None:
        """Validate and dispatch incoming client message."""
        try:
            raw_str = raw_message if isinstance(raw_message, str) else raw_message.decode("utf-8")
            data = json.loads(raw_str)
            msg: ClientMessage = parse_client_message(data)
        except Exception as e:  # noqa: BLE001
            logger.warning("Rejected malformed or invalid message: %s", e)
            await websocket.send(
                ErrorEvent(
                    type="error",
                    message=f"Invalid message format or schema violation: {e}",
                    code="SCHEMA_VALIDATION_ERROR",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ).model_dump_json()
            )
            return

        # Dispatch based on validated message type
        if msg.type == "get_status":
            await self._send_status(websocket)

        elif msg.type == "get_settings":
            await self._send_settings(websocket)

        elif msg.type == "start_listening":
            self.set_state("listening")

        elif msg.type == "stop_listening":
            self.set_state("idle")

        elif msg.type == "execute_command":
            await self._handle_execute_command(websocket, msg)

        elif msg.type == "confirm_action":
            self._handle_confirm_action(msg.action_name, msg.confirmed)

        elif msg.type == "emergency_stop":
            await self._handle_emergency_stop()

        elif msg.type == "toggle_hand_mouse":
            await self._handle_toggle_hand_mouse(websocket, msg)

        elif msg.type == "save_layout":
            await self._handle_save_layout(websocket)

        elif msg.type == "restore_layout":
            await self._handle_restore_layout(websocket)

    async def _send_status(self, websocket: ServerConnection) -> None:
        """Send current system status update."""
        db = LayoutDB()
        snapshots = db.get_snapshots(limit=10)
        recent = self.action_logger.get_recent_logs(limit=10)

        status = StatusUpdateEvent(
            type="status_update",
            mic_active=self._current_state in ("listening", "thinking", "speaking"),
            camera_active=self.hand_mouse.is_running(),
            hand_mouse_active=self.hand_mouse.is_running(),
            offline_mode=True,
            core_running=True,
            active_state=self._current_state,
            recent_commands=recent,
            models={
                "brain": self.config.brain.model_name,
                "stt": self.config.voice.whisper_model,
                "tts": "Piper English",
                "wake_word": self.config.voice.wake_word,
            },
            layout_snapshots_count=len(snapshots),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await websocket.send(status.model_dump_json())

    async def _send_settings(self, websocket: ServerConnection) -> None:
        """Send safe settings and app allowlist."""
        payload = {
            "type": "settings",
            "wake_word": self.config.voice.wake_word,
            "wake_word_hotkey": self.config.voice.wake_word_backup_hotkey,
            "emergency_stop_hotkey": self.config.safety.emergency_stop_hotkey,
            "app_allowlist": self.config.safety.app_allowlist,
            "destructive_actions": self.config.safety.destructive_actions,
            "hand_mouse": {
                "sensitivity": self.config.hand_mouse.sensitivity,
                "dead_zone_px": self.config.hand_mouse.dead_zone_px,
                "camera_index": self.config.hand_mouse.camera_index,
            },
            "layout": {
                "autosave_interval_sec": self.config.layout.autosave_interval_sec,
                "max_snapshots": self.config.layout.max_snapshots,
                "autostart_enabled": self.config.layout.autostart_enabled,
            },
        }
        await websocket.send(json.dumps(payload))

    async def _handle_execute_command(self, websocket: ServerConnection, msg: ExecuteCommandRequest) -> None:
        """Handle execution of typed or voice command with state updates."""
        self.set_state("thinking")

        # Security Rule 5: Check if the command targets a dangerous tool
        clean_text = self.router.sanitize_input(msg.text)
        intent = self.router.route_intent(clean_text)
        if intent:
            tool_name = intent[0]
            tool = registry.get(tool_name)
            if tool and tool.is_dangerous and not msg.force_confirmed:
                logger.warning("Command '%s' targets dangerous tool '%s' requiring confirmation.", msg.text, tool_name)
                prompt = f"Are you sure you want to {tool_name.replace('_', ' ')}? Please confirm."
                await self.broadcast_event(
                    ConfirmationRequiredEvent(
                        type="confirmation_required",
                        action_name=tool_name,
                        prompt=prompt,
                        timeout_sec=10.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
                self.set_state("idle")
                await websocket.send(
                    CommandResultEvent(
                        type="command_result",
                        matched=True,
                        success=False,
                        message=f"Action '{tool_name}' requires confirmation.",
                        tool_name=tool_name,
                        data={"requires_confirmation": True, "action_name": tool_name},
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ).model_dump_json()
                )
                return

        # Execute router command
        res = self.router.execute_command(msg.text, force_confirmed=msg.force_confirmed)
        self.set_state("speaking" if res.success else "idle")

        event = CommandResultEvent(
            type="command_result",
            matched=res.matched,
            success=res.success,
            message=res.message,
            tool_name=res.tool_name,
            data=res.data,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await websocket.send(event.model_dump_json())

        # Reset to idle after brief pause if speaking
        if self._current_state == "speaking":
            await asyncio.sleep(1.0)
            self.set_state("idle")

    def _handle_confirm_action(self, action_name: str, confirmed: bool) -> None:
        """Deliver user confirmation response to pending confirmation future."""
        fut = self._pending_confirmations.get(action_name)
        if fut and not fut.done():
            fut.set_result(confirmed)
            logger.info("Confirmation for '%s' resolved to: %s", action_name, confirmed)

    async def _handle_emergency_stop(self) -> None:
        """Instant emergency stop stopping mic, camera, hand mouse, and actions."""
        logger.warning("EMERGENCY STOP received via WebSocket UI!")
        self.emergency_mgr.trigger()
        self.hand_mouse.stop()
        self.set_state("idle")

        event = EmergencyStopEvent(
            type="emergency_stop_triggered",
            message="Emergency stop activated. All hardware and actions halted.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self.broadcast_event(event)

    async def _handle_toggle_hand_mouse(self, websocket: ServerConnection, msg: ToggleHandMouseRequest) -> None:
        """Toggle hand mouse subprocess."""
        if msg.enabled:
            success = self.hand_mouse.start()
            msg_text = "Hand mouse started." if success else "Failed to start hand mouse."
        else:
            self.hand_mouse.stop()
            success = True
            msg_text = "Hand mouse stopped."

        await websocket.send(
            CommandResultEvent(
                type="command_result",
                matched=True,
                success=success,
                message=msg_text,
                tool_name="toggle_hand_mouse",
                data={"hand_mouse_active": self.hand_mouse.is_running()},
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).model_dump_json()
        )
        await self._send_status(websocket)

    async def _handle_save_layout(self, websocket: ServerConnection) -> None:
        """Trigger manual desktop layout save."""
        snap_id = self.auto_saver.capture_and_save(trigger_type="manual")
        success = snap_id > 0
        msg = f"Saved desktop layout (Snapshot #{snap_id})." if success else "Failed to save layout."
        await websocket.send(
            CommandResultEvent(
                type="command_result",
                matched=True,
                success=success,
                message=msg,
                tool_name="save_layout",
                data={"snapshot_id": snap_id},
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).model_dump_json()
        )

    async def _handle_restore_layout(self, websocket: ServerConnection) -> None:
        """Trigger desktop layout restore via RestoreLayoutTool."""
        tool = registry.get("restore_layout")
        if not tool:
            await websocket.send(
                ErrorEvent(
                    type="error",
                    message="Restore layout tool is not registered.",
                    code="TOOL_NOT_FOUND",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ).model_dump_json()
            )
            return

        res = tool.run()
        await websocket.send(
            CommandResultEvent(
                type="command_result",
                matched=True,
                success=res.success,
                message=res.message,
                tool_name="restore_layout",
                data=res.data,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).model_dump_json()
        )

    async def start(self) -> None:
        """Start the WebSocket server on 127.0.0.1:port."""
        logger.info("Starting AGE WebSocket server on ws://%s:%d ...", self.host, self.port)
        self.auto_saver.start()
        self._server = await serve(
            self.handle_connection,
            self.host,
            self.port,
        )
        logger.info("AGE WebSocket server listening on ws://%s:%d (auth required)", self.host, self.port)

    async def stop(self) -> None:
        """Gracefully stop server and connections."""
        logger.info("Stopping AGE WebSocket server...")
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        self.auto_saver.stop(save_on_shutdown=True)
        self.hand_mouse.stop()
        logger.info("AGE WebSocket server stopped.")

    async def serve_forever(self) -> None:
        """Run server continuously until interrupted."""
        await self.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await self.stop()
