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

    provider: str = Field(default="groq")  # "groq" or "ollama"
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="qwen/qwen3.8-27b")
    ollama_endpoint: str = Field(default="http://127.0.0.1:11434")
    model_name: str = Field(default="qwen2.5:3b")
    keep_alive: str = Field(default="-1")
    timeout_seconds: float = Field(default=45.0, gt=0.0)
    max_history_turns: int = Field(default=10, ge=1, le=50)



    @field_validator("ollama_endpoint")
    @classmethod
    def validate_ollama_endpoint(cls, v: str) -> str:
        """Security Rule 1 & 7: Connect to localhost loopback ONLY."""
        clean = v.strip().lower()
        if not clean.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError(f"SECURITY VIOLATION: Ollama endpoint must be localhost/127.0.0.1, got '{v}'.")
        return v.strip()


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


class OneEuroFilterConfig(BaseModel):
    """Parameters for One Euro smoothing filter."""
    min_cutoff: float = Field(default=0.6, gt=0.0)
    beta: float = Field(default=0.003, ge=0.0)
    d_cutoff: float = Field(default=1.0, gt=0.0)


class ActiveRegionConfig(BaseModel):
    """Normalized camera bounds mapped to screen resolution."""
    x_min: float = Field(default=0.12, ge=0.0, le=1.0)
    x_max: float = Field(default=0.88, ge=0.0, le=1.0)
    y_min: float = Field(default=0.12, ge=0.0, le=1.0)
    y_max: float = Field(default=0.88, ge=0.0, le=1.0)


class ResolutionConfig(BaseModel):
    """Camera capture resolution."""
    width: int = Field(default=640, ge=320, le=1920)
    height: int = Field(default=480, ge=240, le=1080)


class HandMouseConfig(BaseModel):
    """Configuration for hand-gesture mouse subprocess."""
    camera_index: int = Field(default=0, ge=0)
    fps_limit: int = Field(default=30, ge=10, le=60)
    resolution: ResolutionConfig = Field(default_factory=ResolutionConfig)
    sensitivity: float = Field(default=1.0, gt=0.0)
    dead_zone_px: float = Field(default=8.0, ge=0.0)
    pinch_threshold: float = Field(default=0.08, gt=0.0)
    drag_delay_sec: float = Field(default=0.45, gt=0.0)
    missing_hand_timeout_sec: float = Field(default=10.0, gt=0.0)
    ipc_host: str = Field(default="127.0.0.1")
    ipc_port: int = Field(default=8766, ge=1024, le=65535)
    smoothing: OneEuroFilterConfig = Field(default_factory=OneEuroFilterConfig)
    active_region: ActiveRegionConfig = Field(default_factory=ActiveRegionConfig)

    @field_validator("ipc_host")
    @classmethod
    def validate_ipc_host(cls, v: str) -> str:
        """Security Rule 1: Bind to loopback 127.0.0.1 only."""
        clean = v.strip().lower()
        if clean not in ("127.0.0.1", "localhost"):
            raise ValueError(f"SECURITY VIOLATION: Hand mouse IPC host must be loopback, got '{v}'.")
        return clean


class LayoutConfig(BaseModel):
    """Desktop layout snapshot and autostart configuration."""
    autosave_interval_sec: int = Field(default=300, ge=30)
    max_snapshots: int = Field(default=10, ge=1, le=100)
    autostart_enabled: bool = Field(default=False)
    task_name: str = Field(default="AGE_Assistant")


class AppConfig(BaseModel):
    """Complete validated configuration tree."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    hand_mouse: HandMouseConfig = Field(default_factory=HandMouseConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)


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
