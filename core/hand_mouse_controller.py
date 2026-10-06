"""Core controller for managing the Hand Mouse subprocess.

Security Rule 1: Communicates over local loopback with per-session token.
Security Rule 2: Launches process using argument list without shell=True.
Security Rule 10: Integrates with EmergencyStop cleanup.
"""

import subprocess  # nosec: B404
import sys
import time
from typing import Any

from core.config import load_config
from core.logger import get_logger
from core.safety.emergency_stop import EmergencyStop
from core.safety.token_manager import read_token
from hand_mouse.ipc import send_hand_mouse_command

logger = get_logger("core.hand_mouse_controller")


class HandMouseController:
    """Manages the lifecycle of the standalone hand mouse process."""

    def __init__(self, emergency_stop: EmergencyStop | None = None) -> None:
        self.config = load_config()
        self.emergency_stop = emergency_stop
        self._process: subprocess.Popen[bytes] | None = None
        self.ipc_host = self.config.hand_mouse.ipc_host
        self.ipc_port = self.config.hand_mouse.ipc_port

        if self.emergency_stop:
            self.emergency_stop.register_subsystem("hand_mouse", self.stop)

    def start(self) -> bool:
        """Launch the hand mouse subprocess safely."""
        if self.is_running():
            logger.info("Hand mouse process is already running.")
            return True

        cmd = [sys.executable, "-m", "hand_mouse.runner"]
        logger.info("Starting hand mouse subprocess: %s", cmd)

        try:
            # Security Rule 2: subprocess argument list without shell=True
            self._process = subprocess.Popen(  # nosec: B603
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.0)  # Brief wait for process and IPC socket initialization
            if self._process.poll() is not None:
                logger.error("Hand mouse process failed to start (exited with code %d).", self._process.returncode)
                self._process = None
                return False

            logger.info("Hand mouse process successfully started (PID: %d).", self._process.pid)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to launch hand mouse process: %s", e)
            self._process = None
            return False

    def stop(self) -> bool:
        """Stop hand mouse via authenticated IPC, with process fallback."""
        if not self.is_running():
            return True

        logger.info("Stopping hand mouse subprocess...")
        token = read_token()

        # 1. Attempt graceful stop via authenticated IPC channel
        if token:
            try:
                resp = send_hand_mouse_command(
                    command="STOP",
                    token=token,
                    host=self.ipc_host,
                    port=self.ipc_port,
                    timeout_sec=1.5,
                )
                if resp.get("success"):
                    logger.info("Graceful IPC stop acknowledged by hand mouse.")
            except Exception as e:  # noqa: BLE001
                logger.debug("IPC stop failed, falling back to process termination: %s", e)

        # 2. Ensure process is terminated
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except Exception as e:  # noqa: BLE001
                logger.debug("Process terminate failed, forcing kill: %s", e)
                try:
                    self._process.kill()
                except Exception as kill_err:  # noqa: BLE001
                    logger.debug("Process kill error: %s", kill_err)

        self._process = None
        logger.info("Hand mouse subprocess stopped.")
        return True

    def get_status(self) -> dict[str, Any]:
        """Query hand mouse status over authenticated IPC."""
        if not self.is_running():
            return {"running": False, "hand_detected": False}

        token = read_token()
        if not token:
            return {"running": True, "error": "No session token available"}

        try:
            return send_hand_mouse_command(
                command="STATUS",
                token=token,
                host=self.ipc_host,
                port=self.ipc_port,
                timeout_sec=1.5,
            )
        except Exception as e:  # noqa: BLE001
            return {"running": True, "ipc_error": str(e)}

    def is_running(self) -> bool:
        """Check if hand mouse subprocess is active."""
        return self._process is not None and self._process.poll() is None
