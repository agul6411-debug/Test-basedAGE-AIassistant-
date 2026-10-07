"""Background Auto-Save Daemon for Desktop Layout.

Auto-saves desktop snapshots every 5 minutes and on clean shutdown signal.
"""

import atexit
import signal
import threading
import time
from typing import Any

from core.config import load_config
from core.layout.db import LayoutDB
from core.layout.icon_manager import DesktopIconManager
from core.layout.window_manager import WindowManager
from core.logger import get_logger

logger = get_logger("layout.autosave")


class LayoutAutoSaver:
    """Manages periodic layout auto-saving and clean shutdown snapshot capture."""

    def __init__(
        self,
        db: LayoutDB | None = None,
        window_mgr: WindowManager | None = None,
        icon_mgr: DesktopIconManager | None = None,
        interval_sec: int | None = None,
        max_snapshots: int | None = None,
    ) -> None:
        self.config = load_config()
        self.db = db or LayoutDB()
        self.window_mgr = window_mgr or WindowManager()
        self.icon_mgr = icon_mgr or DesktopIconManager()

        layout_cfg = self.config.layout
        self.interval_sec = interval_sec or layout_cfg.autosave_interval_sec
        self.max_snapshots = max_snapshots or layout_cfg.max_snapshots

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._register_shutdown_hooks()

    def capture_and_save(self, trigger_type: str = "autosave") -> int:
        """Capture current windows and icons and persist to database.

        Args:
            trigger_type: 'manual', 'autosave', or 'shutdown'.

        Returns:
            Snapshot ID generated.
        """
        with self._lock:
            try:
                windows = self.window_mgr.get_open_windows()
                icons = self.icon_mgr.get_icon_positions()
                snapshot_id = self.db.save_snapshot(
                    trigger_type=trigger_type,
                    windows=windows,
                    icons=icons,
                    max_snapshots=self.max_snapshots,
                )
                return snapshot_id
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to capture and save layout snapshot (%s): %s", trigger_type, e)
                return -1

    def _loop(self) -> None:
        """Background thread execution loop sleeping for interval_sec."""
        logger.info("Layout auto-saver active (interval: %ds).", self.interval_sec)
        while self._running:
            # Sleep in small increments for responsive shutdown
            for _ in range(self.interval_sec):
                if not self._running:
                    return
                time.sleep(1.0)

            if self._running:
                logger.info("Auto-saver triggering scheduled desktop snapshot...")
                self.capture_and_save(trigger_type="autosave")

    def start(self) -> None:
        """Start background auto-save thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="LayoutAutoSaver")
        self._thread.start()

    def stop(self, save_on_shutdown: bool = True) -> None:
        """Stop background auto-save and optionally record shutdown snapshot."""
        if not self._running:
            return
        self._running = False
        if save_on_shutdown:
            logger.info("Capturing clean shutdown layout snapshot...")
            self.capture_and_save(trigger_type="shutdown")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _register_shutdown_hooks(self) -> None:
        """Register signal and exit handlers for clean shutdown capture."""
        atexit.register(self.stop, save_on_shutdown=True)

        def _sig_handler(signum: int, frame: Any) -> None:
            self.stop(save_on_shutdown=True)

        try:
            signal.signal(signal.SIGINT, _sig_handler)
            signal.signal(signal.SIGTERM, _sig_handler)
        except (ValueError, AttributeError):
            pass
