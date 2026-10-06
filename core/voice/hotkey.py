"""Global hotkey trigger using pynput.

Architecture:
Hotkey Ctrl+Space serves as the backup trigger for wake word detection.
"""

import threading
from collections.abc import Callable

from pynput import keyboard

from core.logger import get_logger

logger = get_logger("voice.hotkey")


class HotkeyTrigger:
    """Listens globally for Ctrl+Space and signals trigger events."""

    def __init__(self, on_trigger: Callable[[], None] | None = None) -> None:
        """Initialize HotkeyTrigger.

        Args:
            on_trigger: Optional callback invoked immediately when Ctrl+Space is pressed.
        """
        self._on_trigger = on_trigger
        self._event = threading.Event()
        self._listener: keyboard.GlobalHotKeys | None = None
        self._is_running = False
        self._lock = threading.Lock()

    def _handle_hotkey(self) -> None:
        """Internal callback when Ctrl+Space is detected."""
        logger.info("Backup hotkey trigger activated: Ctrl+Space")
        self._event.set()
        if self._on_trigger:
            try:
                self._on_trigger()
            except Exception as e:  # noqa: BLE001
                logger.error("Error in hotkey callback: %s", e)

    def start(self) -> None:
        """Start listening for the global hotkey in the background."""
        with self._lock:
            if self._is_running:
                return

            self._listener = keyboard.GlobalHotKeys({
                "<ctrl>+<space>": self._handle_hotkey
            })
            self._listener.daemon = True
            self._listener.start()
            self._is_running = True
            logger.info("Global hotkey listener started for <ctrl>+<space>.")

    def stop(self) -> None:
        """Stop global hotkey listener."""
        with self._lock:
            if not self._is_running:
                return

            if self._listener:
                self._listener.stop()
                self._listener = None

            self._is_running = False
            self._event.clear()
            logger.info("Global hotkey listener stopped.")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the hotkey to be triggered.

        Args:
            timeout: Maximum seconds to wait, or None to wait indefinitely.

        Returns:
            True if hotkey was triggered, False on timeout.
        """
        triggered = self._event.wait(timeout=timeout)
        if triggered:
            self._event.clear()
        return triggered

    def trigger(self) -> None:
        """Programmatically trigger the hotkey event (useful for tests and IPC)."""
        self._handle_hotkey()

    @property
    def is_triggered(self) -> bool:
        """Whether the trigger event has been flagged."""
        return self._event.is_set()
