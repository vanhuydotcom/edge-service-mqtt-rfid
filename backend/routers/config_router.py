"""Configuration API Router for RFID Edge Service.

Handles configuration get, update, and reload endpoints.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from config import EdgeConfig, get_config, reload_config, save_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/config", tags=["config"])


async def verify_token(x_edge_token: Annotated[str | None, Header()] = None) -> None:
    """Verify authentication token if auth is enabled."""
    config = get_config()
    if config.auth.enabled:
        if not x_edge_token or x_edge_token != config.auth.token:
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")


class ConfigUpdateRequest(BaseModel):
    """Request body for configuration update."""

    mqtt: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    ttl: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None


class ConfigResponse(BaseModel):
    """Response containing current configuration."""

    ok: bool = True
    config: dict[str, Any]


class ReloadResponse(BaseModel):
    """Response for configuration reload."""

    ok: bool = True
    message: str = "Configuration reloaded"


@router.get("", response_model=ConfigResponse)
async def get_current_config(
    _: Annotated[None, Depends(verify_token)],
) -> ConfigResponse:
    """Get current service configuration.

    Returns all configurable settings including MQTT, gate, TTL, and decision parameters.
    """
    config = get_config()

    # Return config without sensitive data
    config_dict = config.model_dump()
    if config_dict.get("mqtt", {}).get("password"):
        config_dict["mqtt"]["password"] = "***"
    if config_dict.get("auth", {}).get("token"):
        config_dict["auth"]["token"] = "***"

    return ConfigResponse(ok=True, config=config_dict)


@router.put("", response_model=ConfigResponse)
async def update_config(
    request: ConfigUpdateRequest,
    _: Annotated[None, Depends(verify_token)],
) -> ConfigResponse:
    """Update service configuration.

    Partial updates are supported - only provided fields will be updated.
    Changes are persisted to the configuration file.
    """
    config = get_config()
    config_dict = config.model_dump()

    # Merge updates
    if request.mqtt:
        config_dict["mqtt"].update(request.mqtt)
    if request.gate:
        config_dict["gate"].update(request.gate)
    if request.ttl:
        config_dict["ttl"].update(request.ttl)
    if request.decision:
        config_dict["decision"].update(request.decision)

    # Validate and save
    try:
        new_config = EdgeConfig.model_validate(config_dict)
        save_config(new_config)
        logger.info("Configuration updated successfully")
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}") from e

    # Return updated config (mask sensitive fields)
    result_dict = new_config.model_dump()
    if result_dict.get("mqtt", {}).get("password"):
        result_dict["mqtt"]["password"] = "***"
    if result_dict.get("auth", {}).get("token"):
        result_dict["auth"]["token"] = "***"

    return ConfigResponse(ok=True, config=result_dict)


@router.post("/reload", response_model=ReloadResponse)
async def reload_config_endpoint(
    _: Annotated[None, Depends(verify_token)],
) -> ReloadResponse:
    """Reload configuration from file.

    Hot-reloads the configuration without restarting the service.
    Note: Some settings may require a full restart to take effect (e.g., HTTP port).
    """
    try:
        reload_config()
        logger.info("Configuration reloaded from file")
        return ReloadResponse(ok=True, message="Configuration reloaded successfully")
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload: {e}") from e

