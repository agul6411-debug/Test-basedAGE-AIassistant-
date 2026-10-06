"""Unit tests for safety modules: ConfirmationManager, ActionLogger, EmergencyStop."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.safety.emergency_stop import EmergencyStop

# ==============================================================================
# ConfirmationManager Tests
# ==============================================================================

def test_confirmation_affirmative_response():
    mgr = ConfirmationManager(default_timeout_sec=5.0)
    for word in ["yes", "confirm", "proceed", "sure", "do it", "yep", "yeah"]:
        assert mgr.request_confirmation("shutdown", input_provider=lambda _, w=word: w) is True


def test_confirmation_negative_response():
    mgr = ConfirmationManager(default_timeout_sec=5.0)
    for word in ["no", "cancel", "stop", "abort", "don't", "never", "nope"]:
        assert mgr.request_confirmation("restart", input_provider=lambda _, w=word: w) is False


def test_confirmation_timeout_returns_false():
    mgr = ConfirmationManager(default_timeout_sec=0.1)
    # Callback returns None (no response from user)
    assert mgr.request_confirmation("close_all", input_provider=lambda _: None) is False


def test_confirmation_with_mock_voice_pipeline():
    mgr = ConfirmationManager(default_timeout_sec=5.0)
    mock_voice = MagicMock()
    mock_voice.listen.return_value = "yes please"

    res = mgr.request_confirmation(
        "shutdown",
        prompt="Confirm shutdown?",
        voice_pipeline=mock_voice,
    )
    assert res is True
    mock_voice.speak.assert_called_once_with("Confirm shutdown?")
    mock_voice.listen.assert_called_once()


def test_confirmation_voice_speak_failure_handled():
    mgr = ConfirmationManager(default_timeout_sec=5.0)
    mock_voice = MagicMock()
    mock_voice.speak.side_effect = RuntimeError("Audio device busy")
    mock_voice.listen.return_value = "no"

    res = mgr.request_confirmation("restart", voice_pipeline=mock_voice)
    assert res is False


# ==============================================================================
# ActionLogger Tests
# ==============================================================================

def test_action_logger_masks_sensitive_data(tmp_path: Path):
    log_file = tmp_path / "data" / "logs" / "actions.log"
    logger = ActionLogger(log_file=log_file, base_dir=tmp_path)

    params = {
        "text": "SuperSecretPassword123",
        "api_key": "sk-1234567890abcdef",
        "app_name": "notepad",
        "level": 40,
    }

    entry = logger.log(
        action="type_text",
        parameters=params,
        result="Typed 22 characters",
        success=True,
    )

    # Check sanitized entry
    assert entry["parameters"]["text"] == "[SENSITIVE_TEXT_MASKED len=22]"
    assert entry["parameters"]["api_key"] == "[SENSITIVE_TEXT_MASKED len=19]"
    assert entry["parameters"]["app_name"] == "notepad"
    assert entry["parameters"]["level"] == 40

    # Check written file contents
    assert log_file.exists()
    with open(log_file, "r", encoding="utf-8") as f:
        line = f.readline().strip()
        data = json.loads(line)
        assert data["action"] == "type_text"
        assert "SuperSecretPassword123" not in line
        assert "sk-1234567890abcdef" not in line
        assert data["parameters"]["app_name"] == "notepad"


def test_action_logger_non_string_sensitive():
    logger = ActionLogger()
    sanitized = logger._sanitize_params({"token": 12345})
    assert sanitized["token"] == "[SENSITIVE_DATA_MASKED]"


# ==============================================================================
# EmergencyStop Tests
# ==============================================================================

def test_emergency_stop_lifecycle():
    stop = EmergencyStop()
    assert not stop.is_triggered()

    called = []
    stop.register_subsystem("mic", lambda: called.append("mic"))
    stop.register_subsystem("camera", lambda: called.append("camera"))
    stop.register_subsystem("mouse", lambda: called.append("mouse"))

    stop.trigger()
    assert stop.is_triggered()
    assert set(called) == {"mic", "camera", "mouse"}

    # Reset
    stop.reset()
    assert not stop.is_triggered()


def test_emergency_stop_error_isolation():
    stop = EmergencyStop()
    called = []

    def failing_cb():
        raise RuntimeError("Subsystem error")

    stop.register_subsystem("broken", failing_cb)
    stop.register_subsystem("working", lambda: called.append("working"))

    # Should not raise exception
    stop.trigger()
    assert stop.is_triggered()
    assert called == ["working"]


def test_emergency_stop_unregister():
    stop = EmergencyStop()
    called = []
    stop.register_subsystem("mic", lambda: called.append("mic"))
    stop.unregister_subsystem("mic")

    stop.trigger()
    assert called == []
