"""Rotating file logger with sensitive data masking.

Security Rule 12:
Log actions (what, when, result) but never log full transcripts of sensitive text typed by the user.

Security Rule 13:
Logs live only inside data/.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.safety.path_validator import validate_path_within_root

# Regex patterns for sensitive tokens, keys, passwords to mask in logs
SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(token[=:\s]+)([A-Za-z0-9_\-]{8,})'),
    re.compile(r'(?i)(key[=:\s]+)([A-Za-z0-9_\-]{8,})'),
    re.compile(r'(?i)(password[=:\s]+)([^\s,;]+)'),
    re.compile(r'(?i)(secret[=:\s]+)([A-Za-z0-9_\-]{8,})'),
]


class SensitiveDataMaskingFormatter(logging.Formatter):
    """Logging formatter that masks tokens, passwords, and sensitive keys."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        sanitized = original
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub(r'\1***MASKED***', sanitized)
        return sanitized


def get_logger(name: str = "age") -> logging.Logger:
    """Retrieve an application logger instance.

    Args:
        name: Logger hierarchy name.

    Returns:
        logging.Logger instance.
    """
    return logging.getLogger(name)


def setup_logger(
    log_file: str | Path = "data/logs/age.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    log_level: str = "INFO",
    base_dir: str | Path | None = None,
    logger_name: str = "age",
) -> logging.Logger:
    """Configure AGE logger with RotatingFileHandler and ConsoleHandler.

    Args:
        log_file: Path to the log file (must resolve inside data/logs).
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to retain.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        base_dir: Base project root directory.
        logger_name: Logger hierarchy name.

    Returns:
        Configured logging.Logger.
    """
    root = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    logs_dir = root / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Security Rule 13: Strictly confine log files to data/logs
    safe_log_path = validate_path_within_root(log_file, logs_dir)

    logger = logging.getLogger(logger_name)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Safely close and clear any pre-existing handlers on this logger
    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)
        existing_handler.close()

    formatter = SensitiveDataMaskingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler
    file_handler = RotatingFileHandler(
        filename=str(safe_log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)

    return logger
