"""Windows Task Scheduler logon autostart manager for normal user.

Security Rule 2: Subprocess argument lists without shell=True.
Security Rule 9: Runs strictly as normal user, never requesting admin privileges.
"""

import sys
from pathlib import Path

from core.config import load_config
from core.logger import get_logger
from core.safety.process_runner import SafeProcessRunner

logger = get_logger("layout.autostart")

DEFAULT_TASK_NAME = "AGE_Assistant"


class AutostartManager:
    """Manages Windows Task Scheduler logon entries for the normal user."""

    def __init__(self, task_name: str | None = None) -> None:
        self.config = load_config()
        self.task_name = task_name or self.config.layout.task_name or DEFAULT_TASK_NAME

    def is_enabled(self) -> bool:
        """Check whether the Task Scheduler entry exists."""
        cmd = ["schtasks", "/query", "/tn", self.task_name]
        try:
            res = SafeProcessRunner.run_command(cmd)
            return res.returncode == 0
        except Exception as e:  # noqa: BLE001
            logger.debug("schtasks query failed: %s", e)
            return False

    def enable(self, script_path: str | Path | None = None) -> bool:
        """Create or update Task Scheduler task to run at user logon as NORMAL user.

        Args:
            script_path: Path to startup script (default: demo_voice.py).

        Returns:
            True if task creation succeeded.
        """
        python_exe = sys.executable
        root_dir = Path.cwd().resolve()
        script = Path(script_path).resolve() if script_path else root_dir / "demo_voice.py"

        # Construct safe command line for schtasks
        task_run = f'"{python_exe}" "{script}"'

        cmd = [
            "schtasks",
            "/create",
            "/tn",
            self.task_name,
            "/tr",
            task_run,
            "/sc",
            "onlogon",
            "/f",
        ]

        logger.info("Enabling autostart via Task Scheduler: %s", self.task_name)
        try:
            res = SafeProcessRunner.run_command(cmd)
            if res.returncode == 0:
                logger.info("Autostart task '%s' created successfully.", self.task_name)
                return True
            logger.error("schtasks /create returned code %d: %s", res.returncode, res.stderr)
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to enable autostart task: %s", e)
            return False

    def disable(self) -> bool:
        """Remove Task Scheduler task."""
        cmd = ["schtasks", "/delete", "/tn", self.task_name, "/f"]
        logger.info("Disabling autostart task: %s", self.task_name)
        try:
            res = SafeProcessRunner.run_command(cmd)
            if res.returncode == 0:
                logger.info("Autostart task '%s' deleted successfully.", self.task_name)
                return True
            logger.debug("schtasks /delete returned code %d: %s", res.returncode, res.stderr)
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to delete autostart task: %s", e)
            return False

    def sync_with_config(self) -> bool:
        """Apply autostart setting specified in config.yaml."""
        should_enable = self.config.layout.autostart_enabled
        if should_enable:
            return self.enable()
        return self.disable()
