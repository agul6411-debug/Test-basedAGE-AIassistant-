"""Local loopback IPC server and client for hand mouse process control.

Security Rule 1: Binds strictly to 127.0.0.1 ONLY, never 0.0.0.0.
Requires per-session auth token verification.
"""

import json
import socket
import threading
from collections.abc import Callable
from typing import Any

from core.logger import get_logger
from core.safety.token_manager import verify_token

logger = get_logger("hand_mouse.ipc")


class HandMouseIPCServer:
    """Loopback socket server receiving commands from the core process."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8766,
        command_handler: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize IPC server.

        Args:
            host: Loopback IP address (must be 127.0.0.1).
            port: Port to listen on.
            command_handler: Callback handling verified commands.
        """
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"SECURITY VIOLATION: Hand mouse IPC server must bind to 127.0.0.1, got '{host}'.")

        self.host = host
        self.port = port
        self.command_handler = command_handler
        self._server_sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start listening for local connections in a daemon thread."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(5)
        self._server_sock.settimeout(1.0)
        self._running = True

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Hand mouse IPC server listening on %s:%d.", self.host, self.port)

    def _listen_loop(self) -> None:
        while self._running:
            try:
                conn, addr = self._server_sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            # Handle client connection
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        try:
            conn.settimeout(3.0)
            data = conn.recv(4096).decode("utf-8")
            if not data:
                return

            req = json.loads(data)
            token = req.get("token", "")
            cmd = req.get("command", "")

            # Security Rule 1: Authenticate with per-session token
            if not verify_token(token):
                logger.warning("Rejected unauthorized IPC connection from %s", addr)
                resp = {"success": False, "error": "Unauthorized: Invalid session token"}
            else:
                if self.command_handler:
                    resp = self.command_handler(cmd)
                else:
                    resp = {"success": True, "message": f"Command '{cmd}' received"}

            conn.sendall(json.dumps(resp).encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.error("IPC client error from %s: %s", addr, e)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Stop IPC server and close socket."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


def send_hand_mouse_command(
    command: str,
    token: str,
    host: str = "127.0.0.1",
    port: int = 8766,
    timeout_sec: float = 2.0,
) -> dict[str, Any]:
    """Send an authenticated command to the hand mouse subprocess.

    Args:
        command: Command string (e.g. 'STATUS', 'STOP', 'PAUSE').
        token: Current session auth token.
        host: Loopback host.
        port: Subprocess IPC port.
        timeout_sec: Connection timeout in seconds.

    Returns:
        Response dictionary from subprocess.
    """
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"SECURITY VIOLATION: IPC client must connect to loopback, got '{host}'.")

    payload = json.dumps({"command": command, "token": token}).encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    try:
        sock.connect((host, port))
        sock.sendall(payload)
        resp_data = sock.recv(4096).decode("utf-8")
        return json.loads(resp_data)
    finally:
        sock.close()
