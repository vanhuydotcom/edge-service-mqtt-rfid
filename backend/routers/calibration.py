"""Calibration API Router for RFID Edge Service.

Handles antenna power, inventory control, and alarm testing endpoints.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from config import get_config
from models import AntennaPowerRequest
from mqtt_client import get_mqtt_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/calibration", tags=["calibration"])


async def verify_token(x_edge_token: Annotated[str | None, Header()] = None) -> None:
    """Verify authentication token if auth is enabled."""
    config = get_config()
    if config.auth.enabled:
        if not x_edge_token or x_edge_token != config.auth.token:
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")


class CalibrationResponse(BaseModel):
    """Standard calibration response."""

    ok: bool = True
    message: str


@router.post("/start", response_model=CalibrationResponse)
async def start_inventory(
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Start RFID inventory scan on gate reader.

    Begins continuous tag reading for calibration and testing purposes.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    await mqtt.send_rfid_command("start")
    logger.info("Inventory scan started")

    return CalibrationResponse(ok=True, message="Inventory scan started")


@router.post("/stop", response_model=CalibrationResponse)
async def stop_inventory(
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Stop RFID inventory scan on gate reader.

    Stops continuous tag reading.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    await mqtt.send_rfid_command("stop")
    logger.info("Inventory scan stopped")

    return CalibrationResponse(ok=True, message="Inventory scan stopped")


@router.post("/power", response_model=CalibrationResponse)
async def set_antenna_power(
    request: AntennaPowerRequest,
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Set antenna power levels.

    Adjusts transmit power for each antenna (0-30 dBm).
    Higher power = longer read range but may cause interference.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    await mqtt.set_antenna_power(
        antenna1=request.antenna1,
        antenna2=request.antenna2,
        antenna3=request.antenna3,
        antenna4=request.antenna4,
    )

    logger.info(
        f"Antenna power set: {request.antenna1}/{request.antenna2}/{request.antenna3}/{request.antenna4}"
    )

    return CalibrationResponse(
        ok=True,
        message=f"Antenna power set: {request.antenna1}/{request.antenna2}/{request.antenna3}/{request.antenna4} dBm",
    )


@router.post("/test-alarm", response_model=CalibrationResponse)
async def test_alarm(
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Test alarm by triggering GPO pulse.

    Triggers a test alarm pulse on the gate reader for verification.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    config = get_config()
    await mqtt.trigger_alarm(duration=config.gate.gpo_pulse_seconds)

    logger.info("Test alarm triggered")

    return CalibrationResponse(
        ok=True,
        message=f"Test alarm triggered ({config.gate.gpo_pulse_seconds}s pulse)",
    )


@router.get("/power", response_model=CalibrationResponse)
async def get_antenna_power(
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Query current antenna power levels from gate reader.

    Sends a query to the reader. Response will be sent via WebSocket
    as COMMAND_RESPONSE event and stored in the MQTT client.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    await mqtt.get_antenna_power()
    logger.info("Antenna power query requested")

    return CalibrationResponse(
        ok=True,
        message="Antenna power query sent. Response will arrive via WebSocket.",
    )


@router.get("/status", response_model=CalibrationResponse)
async def get_reader_status(
    _: Annotated[None, Depends(verify_token)],
) -> CalibrationResponse:
    """Query reader status including inventory state and connected antennas.

    Sends a status query to the reader. Response will be sent via WebSocket
    as COMMAND_RESPONSE event.
    """
    mqtt = get_mqtt_client()

    if not mqtt.is_connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    await mqtt.get_reader_status()
    logger.info("Reader status query requested")

    return CalibrationResponse(
        ok=True,
        message="Reader status query sent. Response will arrive via WebSocket.",
    )

