"""Action audit logger with sensitive content sanitization.

Security Rule 12:
Log actions (what, when, result) but never log full transcripts
of sensitive text typed by the user.

Security Rule 13:
Logs live only inside data/.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.safety.path_validator import validate_path_within_root

SENSITIVE_KEYS = {"text", "password", "token", "secret", "key", "auth", "credential"}


class ActionLogger:
    """Audit logger writing structured action entries with sensitive content masking."""

    def __init__(self, log_file: str | Path = "data/logs/actions.log", base_dir: str | Path | None = None) -> None:
        """Initialize ActionLogger.

        Args:
            log_file: Relative path to action log file inside data/.
            base_dir: Optional root directory confinement.
        """
        root = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
        data_root = (root / "data").resolve()
        data_root.mkdir(parents=True, exist_ok=True)
        target = (root / log_file).resolve() if not Path(log_file).is_absolute() else Path(log_file).resolve()
        self.log_path = validate_path_within_root(target, data_root)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive strings like typed text, passwords, or tokens."""
        sanitized = {}
        for k, v in params.items():
            key_lower = k.lower()
            if any(s in key_lower for s in SENSITIVE_KEYS):
                if isinstance(v, str):
                    sanitized[k] = f"[SENSITIVE_TEXT_MASKED len={len(v)}]"
                else:
                    sanitized[k] = "[SENSITIVE_DATA_MASKED]"
            else:
                sanitized[k] = v
        return sanitized

    def log(
        self,
        action: str,
        parameters: dict[str, Any],
        result: str,
        success: bool = True,
    ) -> dict[str, Any]:
        """Record an action execution event.

        Args:
            action: Name of the action or tool executed.
            parameters: Input arguments passed to the action.
            result: Human-readable result or error description.
            success: Whether the action completed successfully.

        Returns:
            The logged event dictionary.
        """
        clean_params = self._sanitize_params(parameters)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "parameters": clean_params,
            "result": result,
            "success": success,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry
