"""Tests for configuration loading and validation."""


import pytest

from core.config import ServerConfig, load_config


def test_load_default_config():
    config = load_config()
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8765
    for expected_app in ["notepad", "calc", "chrome", "edge", "explorer", "vscode"]:
        assert expected_app in config.safety.app_allowlist
    assert "shutdown" in config.safety.destructive_actions
    assert config.safety.emergency_stop_hotkey == "ctrl+shift+esc"
    assert config.logging.log_file == "data/logs/age.log"
    assert config.logging.max_bytes > 0
    assert config.layout.autosave_interval_sec == 300
    assert config.layout.max_snapshots == 10
    assert config.layout.autostart_enabled is False
    assert config.layout.task_name == "AGE_Assistant"


def test_server_config_rejects_wildcard():
    with pytest.raises(ValueError, match="never 0.0.0.0"):
        ServerConfig(host="0.0.0.0")


def test_server_config_rejects_external_ip():
    with pytest.raises(ValueError, match="not a local loopback"):
        ServerConfig(host="192.168.1.100")


def test_server_config_accepts_loopback():
    sc1 = ServerConfig(host="127.0.0.1")
    assert sc1.host == "127.0.0.1"
    sc2 = ServerConfig(host="localhost")
    assert sc2.host == "localhost"
