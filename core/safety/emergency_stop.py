"""Emergency stop handler and hotkey listener.

Security Rule 10:
Add an emergency-stop hotkey (Ctrl+Shift+Esc) that stops mic, camera,
hand mouse, and any running action immediately.
"""

import threading
from collections.abc import Callable

from pynput import keyboard

from core.logger import get_logger

logger = get_logger("safety.emergency_stop")


class EmergencyStop:
    """Coordinates immediate shutdown of active sensors, processes, and actions."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._listener: keyboard.GlobalHotKeys | None = None
        self._lock = threading.Lock()

    def register_subsystem(self, name: str, stop_callback: Callable[[], None]) -> None:
        """Register a subsystem cleanup callback.

        Args:
            name: Subsystem identifier (e.g. 'mic', 'camera', 'mouse').
            stop_callback: Zero-argument function invoked during emergency stop.
        """
        with self._lock:
            self._callbacks[name] = stop_callback

    def unregister_subsystem(self, name: str) -> None:
        """Unregister a subsystem cleanup callback."""
        with self._lock:
            self._callbacks.pop(name, None)

    def trigger(self) -> None:
        """Immediately trigger emergency stop and shut down all registered subsystems."""
        logger.critical("EMERGENCY STOP TRIGGERED! Halting all running operations immediately.")
        self._stop_event.set()

        with self._lock:
            for name, cb in list(self._callbacks.items()):
                try:
                    logger.warning("Halting subsystem '%s'...", name)
                    cb()
                except Exception as e:  # noqa: BLE001
                    logger.error("Error stopping subsystem '%s': %s", name, e)

    def start_hotkey_listener(self) -> None:
        """Listen globally for Ctrl+Shift+Esc emergency-stop combination."""
        with self._lock:
            if self._listener is not None:
                return

            try:
                self._listener = keyboard.GlobalHotKeys({
                    "<ctrl>+<shift>+<esc>": self.trigger
                })
                self._listener.daemon = True
                self._listener.start()
                logger.info("Emergency-stop listener active for <ctrl>+<shift>+<esc>.")
            except Exception as e:  # noqa: BLE001
                logger.error("Could not register emergency stop hotkey: %s", e)

    def stop_hotkey_listener(self) -> None:
        """Stop listening for emergency-stop combination."""
        with self._lock:
            if self._listener:
                self._listener.stop()
                self._listener = None

    def is_triggered(self) -> bool:
        """Check whether emergency stop has been activated."""
        return self._stop_event.is_set()

    def reset(self) -> None:
        """Reset emergency stop state after resolution."""
        self._stop_event.clear()
        logger.info("Emergency stop flag reset.")
