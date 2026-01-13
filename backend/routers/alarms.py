"""Alarms API Router for RFID Edge Service.

Handles alarm history and export endpoints.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from config import get_config
from database import get_alarms_paginated
from models import AlarmEvent, AlarmListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/alarms", tags=["alarms"])


async def verify_token(x_edge_token: Annotated[str | None, Header()] = None) -> None:
    """Verify authentication token if auth is enabled."""
    config = get_config()
    if config.auth.enabled:
        if not x_edge_token or x_edge_token != config.auth.token:
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")


def _parse_date(date_str: str | None) -> int | None:
    """Parse date string to Unix timestamp.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Unix timestamp or None.
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return None


@router.get("", response_model=AlarmListResponse)
async def get_alarms(
    _: Annotated[None, Depends(verify_token)],
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    from_date: str | None = Query(default=None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str | None = Query(default=None, alias="to", description="End date (YYYY-MM-DD)"),
) -> AlarmListResponse:
    """Get paginated alarm history.

    Returns list of alarm events with pagination support.
    Optionally filter by date range.
    """
    from_ts = _parse_date(from_date)
    to_ts = _parse_date(to_date)

    # Adjust to_ts to end of day
    if to_ts:
        to_ts += 86400 - 1

    items, total = await get_alarms_paginated(
        page=page,
        limit=limit,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    # Convert to AlarmEvent models
    alarm_events = []
    for item in items:
        alarm_events.append(
            AlarmEvent(
                id=item["id"],
                gate_id=item["gate_id"],
                epc=item["epc"],
                qr_code=item.get("qr_code"),
                rssi=item.get("rssi"),
                antenna=item.get("antenna"),
                created_at=datetime.fromtimestamp(item["created_at"], tz=timezone.utc),
            )
        )

    return AlarmListResponse(
        items=alarm_events,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/export")
async def export_alarms(
    _: Annotated[None, Depends(verify_token)],
    from_date: str | None = Query(default=None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str | None = Query(default=None, alias="to", description="End date (YYYY-MM-DD)"),
) -> StreamingResponse:
    """Export alarm history to CSV.

    Downloads all alarms within the date range as a CSV file.
    """
    from_ts = _parse_date(from_date)
    to_ts = _parse_date(to_date)

    if to_ts:
        to_ts += 86400 - 1

    # Get all alarms (no pagination for export)
    items, _ = await get_alarms_paginated(
        page=1,
        limit=10000,  # Max export size
        from_ts=from_ts,
        to_ts=to_ts,
    )

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["ID", "Gate ID", "EPC", "QR Code", "RSSI", "Antenna", "Created At"])

    # Write data
    for item in items:
        created_at = datetime.fromtimestamp(item["created_at"], tz=timezone.utc)
        writer.writerow([
            item["id"],
            item["gate_id"],
            item["epc"],
            item.get("qr_code", ""),
            item.get("rssi", ""),
            item.get("antenna", ""),
            created_at.isoformat(),
        ])

    output.seek(0)

    # Generate filename
    filename = f"alarms_{from_date or 'all'}_{to_date or 'now'}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

