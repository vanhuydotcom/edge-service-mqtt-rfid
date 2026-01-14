"""Pydantic models for RFID Edge Service API.

All request/response schemas following OpenAPI documentation standards.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TagState(str, Enum):
    """Possible states for an RFID tag."""

    IN_CART = "IN_CART"
    PAID = "PAID"


class Decision(str, Enum):
    """Gate decision outcomes."""

    PASS = "PASS"
    ALARM = "ALARM"


# --- Request Models ---


class TagsInCartRequest(BaseModel):
    """Request body for registering tags in cart.

    POS sends QR codes (the canonical identifier).
    Database stores QR codes directly.
    Security gate: scans EPC → Edge Service decodes to QR → matches against stored QRs.
    """

    store_id: str = Field(..., description="Store identifier")
    pos_id: str = Field(..., description="POS terminal identifier")
    order_id: str = Field(..., description="Order identifier")
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=86400, description="Time-to-live in seconds (uses config default if not provided)")
    qr_codes: list[str] = Field(..., min_length=1, description="List of QR codes to register")


class TagsPaidRequest(BaseModel):
    """Request body for registering paid tags.

    POS sends QR codes. Database stores QR codes.
    """

    store_id: str = Field(..., description="Store identifier")
    pos_id: str = Field(..., description="POS terminal identifier")
    order_id: str = Field(..., description="Order identifier")
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=604800, description="Time-to-live in seconds (uses config default if not provided)")
    qr_codes: list[str] = Field(..., min_length=1, description="List of QR codes to register")


class TagsRemoveRequest(BaseModel):
    """Request body for removing tags."""

    order_id: str = Field(..., description="Order identifier")
    qr_codes: list[str] = Field(..., min_length=1, description="List of QR codes to remove")


class AntennaPowerRequest(BaseModel):
    """Request body for setting antenna power levels."""

    antenna1: int = Field(default=20, ge=0, le=30, description="Antenna 1 power (dBm)")
    antenna2: int = Field(default=20, ge=0, le=30, description="Antenna 2 power (dBm)")
    antenna3: int = Field(default=15, ge=0, le=30, description="Antenna 3 power (dBm)")
    antenna4: int = Field(default=15, ge=0, le=30, description="Antenna 4 power (dBm)")


# --- Response Models ---


class TagsInCartResponse(BaseModel):
    """Response for tags in cart registration."""

    ok: bool = True
    upserted: int = Field(..., description="Number of tags inserted/updated")
    ignored_paid: int = Field(default=0, description="Tags ignored because already PAID")
    expires_in_seconds: int = Field(..., description="TTL applied to tags")


class TagsPaidResponse(BaseModel):
    """Response for paid tags registration."""

    ok: bool = True
    upserted: int = Field(..., description="Number of tags inserted/updated")
    expires_in_seconds: int = Field(..., description="TTL applied to tags")


class TagsRemoveResponse(BaseModel):
    """Response for tags removal."""

    ok: bool = True
    deleted: int = Field(..., description="Number of tags deleted")


class TagStatusResponse(BaseModel):
    """Response for individual tag status lookup.

    Can look up by either QR code or EPC (EPC is decoded to QR for matching).
    """

    qr_code: str = Field(..., description="QR code identifier")
    epc: Optional[str] = Field(None, description="Original EPC if lookup was by EPC")
    present: bool
    state: Optional[TagState] = None
    order_id: Optional[str] = None
    pos_id: Optional[str] = None
    ttl_remaining_seconds: Optional[int] = None


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    ok: bool = True
    mqtt_connected: bool
    db_ok: bool
    gate_last_seen_seconds: Optional[int] = None
    uptime_seconds: int = 0


class StatsResponse(BaseModel):
    """Response for statistics endpoint."""

    in_cart_count: int
    paid_count: int
    alarms_last_24h: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    ok: bool = False
    error: dict[str, str] = Field(..., description="Error details with code and message")


# --- Alarm Models ---


class AlarmEvent(BaseModel):
    """Single alarm event record."""

    id: int
    gate_id: str
    epc: str
    qr_code: Optional[str] = None
    rssi: Optional[float] = None
    antenna: Optional[int] = None
    created_at: datetime


class AlarmListResponse(BaseModel):
    """Paginated alarm list response."""

    items: list[AlarmEvent]
    total: int
    page: int
    limit: int


# --- WebSocket Event Models ---


class WSTagDetectedEvent(BaseModel):
    """WebSocket event for tag detection."""

    type: str = "TAG_DETECTED"
    tag_id: str
    rssi: Optional[float] = None
    antenna: Optional[int] = None
    decision: Decision
    timestamp: datetime


class WSAlarmTriggeredEvent(BaseModel):
    """WebSocket event for alarm trigger."""

    type: str = "ALARM_TRIGGERED"
    tag_id: str
    gate_id: str
    rssi: Optional[float] = None
    timestamp: datetime


class WSStatusUpdateEvent(BaseModel):
    """WebSocket event for periodic status updates."""

    type: str = "STATUS_UPDATE"
    mqtt_connected: bool
    in_cart_count: int
    paid_count: int

