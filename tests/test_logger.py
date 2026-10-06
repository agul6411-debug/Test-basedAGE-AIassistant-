"""Unit tests for rotating logger and sensitive data masking."""

import logging
from pathlib import Path

import pytest

from core.logger import SensitiveDataMaskingFormatter, setup_logger
from core.safety.path_validator import PathTraversalError


def test_logger_sensitive_data_masking():
    formatter = SensitiveDataMaskingFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Connecting with token: my_secret_token_123456 and password: supersecretpassword",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "my_secret_token_123456" not in formatted
    assert "supersecretpassword" not in formatted
    assert "***MASKED***" in formatted


def test_logger_creates_log_file(tmp_path: Path):
    log_file = tmp_path / "data" / "logs" / "test_age.log"
    logger = setup_logger(
        log_file="test_age.log",
        max_bytes=1024,
        backup_count=2,
        base_dir=tmp_path,
    )
    logger.info("Test log message: action executed successfully")

    # Flush handlers
    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test log message: action executed successfully" in content

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_logger_rotation(tmp_path: Path):
    log_file = tmp_path / "data" / "logs" / "rotating_age.log"
    # Small max_bytes to force rotation
    logger = setup_logger(
        log_file="rotating_age.log",
        max_bytes=200,
        backup_count=2,
        base_dir=tmp_path,
        logger_name="test_rotation",
    )

    for i in range(20):
        logger.info(f"Writing rotation line {i:03d} to trigger log file rotation")

    for handler in logger.handlers:
        handler.flush()

    rotated_file = tmp_path / "data" / "logs" / "rotating_age.log.1"
    assert log_file.exists()
    assert rotated_file.exists()

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_logger_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(PathTraversalError):
        setup_logger(
            log_file="../../outside.log",
            base_dir=tmp_path,
        )
