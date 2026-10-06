"""Configuration loader and schema validator.

Enforces Security Rule 1 (bind to 127.0.0.1 ONLY) and Rule 4 (app allowlists).
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ServerConfig(BaseModel):
    """Server network and authentication settings."""
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765, ge=1024, le=65535)
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:8765", "http://localhost:8765"])
    token_file: str = Field(default="data/sessions/session.token")

    @field_validator("host")
    @classmethod
    def validate_host_loopback_only(cls, v: str) -> str:
        """Security Rule 1: WebSocket binds to 127.0.0.1 ONLY, never 0.0.0.0."""
        clean = v.strip().lower()
        # Explicitly detecting and forbidding wildcard binding
        if clean in ("0.0.0.0", "::", "all"):  # nosec: B104
            raise ValueError("SECURITY VIOLATION: Server must bind to 127.0.0.1 only, never 0.0.0.0 or wildcard.")
        if clean not in ("127.0.0.1", "localhost"):
            raise ValueError(f"SECURITY VIOLATION: Server host '{v}' is not a local loopback address.")
        return clean


class SafetyConfig(BaseModel):
    """Safety guardrails and execution limits."""
    app_allowlist: dict[str, str] = Field(default_factory=dict)
    destructive_actions: list[str] = Field(default_factory=list)
    emergency_stop_hotkey: str = Field(default="ctrl+shift+esc")

    @field_validator("app_allowlist")
    @classmethod
    def validate_allowlist(cls, v: dict[str, str]) -> dict[str, str]:
        """Normalize keys and validate executable mappings."""
        normalized = {}
        for key, val in v.items():
            clean_key = key.strip().lower()
            clean_val = val.strip()
            if not clean_key or not clean_val:
                raise ValueError("Allowlist keys and executable targets cannot be empty.")
            normalized[clean_key] = clean_val
        return normalized


class VoiceConfig(BaseModel):
    """Voice pipeline configuration."""
    wake_word: str = Field(default="Hey AGE")
    wake_word_backup_hotkey: str = Field(default="ctrl+space")
    vad_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    whisper_model: str = Field(default="base.en")
    sample_rate: int = Field(default=16000, ge=8000, le=48000)


class BrainConfig(BaseModel):
    """Brain routing and local LLM settings."""
    model_config = {"protected_namespaces": ()}

    ollama_endpoint: str = Field(default="http://127.0.0.1:11434")
    model_name: str = Field(default="qwen2.5:3b")
    timeout_seconds: float = Field(default=15.0, gt=0.0)


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    log_file: str = Field(default="data/logs/age.log")
    max_bytes: int = Field(default=5242880, gt=0)
    backup_count: int = Field(default=5, ge=1)
    log_level: str = Field(default="INFO")


class StorageConfig(BaseModel):
    """Storage directories and database paths."""
    data_dir: str = Field(default="data")
    logs_dir: str = Field(default="data/logs")
    sessions_dir: str = Field(default="data/sessions")
    layout_db: str = Field(default="data/layout.db")


class AppConfig(BaseModel):
    """Complete validated configuration tree."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Optional path to config file. Defaults to config.yaml in project root.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If configuration file does not exist.
        ValueError: If YAML is malformed or violates security validation rules.
    """
    path = Path(config_path) if config_path else Path("config.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise TypeError("Configuration YAML must contain a dictionary/mapping at the root.")

    return AppConfig.model_validate(data)
