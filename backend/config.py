"""Configuration management for RFID Edge Service.

Loads configuration from JSON file with environment-based overrides.
Supports hot-reload via API endpoint.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def get_app_dir() -> Path:
    """Get the application directory.

    When running as PyInstaller bundle, returns the directory containing the .exe.
    When running as script, returns the backend directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe directory
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


def get_bundled_resource_dir() -> Path:
    """Get the directory containing bundled resources.

    When running as PyInstaller bundle, returns the _MEIPASS temp directory.
    When running as script, returns the backend directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use temp extraction dir
        return Path(sys._MEIPASS)  # type: ignore
    else:
        # Running as script
        return Path(__file__).parent


class HttpConfig(BaseModel):
    """HTTP server configuration."""

    host: str = "0.0.0.0"
    port: int = 8088


class MqttConfig(BaseModel):
    """MQTT broker configuration."""

    host: str = "127.0.0.1"
    port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False


class GateConfig(BaseModel):
    """Gate reader configuration."""

    client_id: str = "mqttx_1e40cea4"
    topic_tag_stream: str = "reader/{client_id}/stream/tag"
    topic_gpo_cmd: str = "reader/{client_id}/cmd/gpo"
    topic_rfid_cmd: str = "reader/{client_id}/cmd/rfid"
    topic_power_cmd: str = "reader/{client_id}/cmd/power"
    topic_data_response: str = "reader/{client_id}/data/response"
    topic_data_status: str = "reader/{client_id}/data/status"
    gpo_pulse_seconds: int = 5


class TtlConfig(BaseModel):
    """TTL settings for tag states."""

    in_cart_seconds: int = 3600
    paid_seconds: int = 86400
    cleanup_interval_seconds: int = 60


class DecisionConfig(BaseModel):
    """Decision engine configuration."""

    pass_when_in_cart: bool = True
    debounce_ms: int = 2500
    alarm_cooldown_ms: int = 7000


class StorageConfig(BaseModel):
    """Storage configuration."""

    sqlite_path: str = "data/edge.db"


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = False
    token: str = ""


class EdgeConfig(BaseModel):
    """Complete edge service configuration."""

    http: HttpConfig = Field(default_factory=HttpConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    ttl: TtlConfig = Field(default_factory=TtlConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    config_path: str = Field(
        default="conf/edge-config.json",
        description="Path to JSON configuration file",
    )
    env: str = Field(default="production", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_prefix = "EDGE_"


# Global configuration instance
_config: Optional[EdgeConfig] = None
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_config(config_path: Optional[str] = None) -> EdgeConfig:
    """Load configuration from JSON file.

    Args:
        config_path: Optional path to config file. If not provided,
                     uses path from settings.

    Returns:
        EdgeConfig instance with loaded configuration.
    """
    global _config

    settings = get_settings()

    # Determine config file path
    if config_path:
        path = Path(config_path)
    else:
        # Try writable config in app directory first
        app_config = get_app_dir() / settings.config_path
        # Fall back to bundled config
        bundled_config = get_bundled_resource_dir() / settings.config_path

        if app_config.exists():
            path = app_config
        elif bundled_config.exists():
            path = bundled_config
        else:
            path = app_config  # Use app dir for creating new config

    # Try environment-specific config first
    env_path = path.parent / f"{path.stem}.{settings.env}{path.suffix}"
    if env_path.exists():
        path = env_path
        logger.info(f"Using environment config: {env_path}")

    if path.exists():
        logger.info(f"Loading configuration from: {path}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _config = EdgeConfig.model_validate(data)
    else:
        logger.warning(f"Config file not found at {path}, using defaults")
        _config = EdgeConfig()

    return _config


def get_config() -> EdgeConfig:
    """Get current configuration (singleton with lazy load)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> EdgeConfig:
    """Reload configuration from file.

    Returns:
        Newly loaded EdgeConfig instance.
    """
    global _config
    _config = None
    return load_config()


def save_config(config: EdgeConfig, config_path: Optional[str] = None) -> None:
    """Save configuration to JSON file.

    Args:
        config: EdgeConfig instance to save.
        config_path: Optional path to save config. Uses default if not provided.
    """
    global _config

    settings = get_settings()
    path = Path(config_path or settings.config_path)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)

    _config = config
    logger.info(f"Configuration saved to: {path}")

