"""Tags API Router for RFID Edge Service.

Handles QR code registration, payment, and removal endpoints.

Data Flow:
- POS sends QR codes (canonical identifier) to these endpoints
- QR codes are stored in the database
- Security gate reads EPC → decoded to QR → matched against stored QRs
"""

import logging
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from config import get_config
from database import (
    get_qr_state,
    remove_qr_codes,
    upsert_qr_codes_in_cart,
    upsert_qr_codes_paid,
)
from models import (
    TagsInCartRequest,
    TagsInCartResponse,
    TagsPaidRequest,
    TagsPaidResponse,
    TagsRemoveRequest,
    TagsRemoveResponse,
    TagState,
    TagStatusResponse,
)
from services.epc_decoder import decode_epc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tags", tags=["tags"])


async def verify_token(x_edge_token: Annotated[str | None, Header()] = None) -> None:
    """Verify authentication token if auth is enabled.

    Args:
        x_edge_token: Token from request header.

    Raises:
        HTTPException: If auth is enabled and token is invalid.
    """
    config = get_config()
    if config.auth.enabled:
        if not x_edge_token or x_edge_token != config.auth.token:
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")


@router.post("/in-cart", response_model=TagsInCartResponse)
async def register_qr_codes_in_cart(
    request: TagsInCartRequest,
    _: Annotated[None, Depends(verify_token)],
) -> TagsInCartResponse:
    """Register QR codes scanned into shopping cart.

    QR codes in IN_CART state will pass through the gate (if pass_when_in_cart is enabled).
    Does NOT overwrite QR codes that are already in PAID state.
    """
    logger.info(f"Registering {','.join(request.qr_codes)} QR codes in cart for order {request.order_id}")

    # Use config default if ttl_seconds not explicitly provided in request
    config = get_config()
    ttl_seconds = request.ttl_seconds if request.ttl_seconds is not None else config.ttl.in_cart_seconds

    upserted, ignored_paid = await upsert_qr_codes_in_cart(
        qr_codes=request.qr_codes,
        order_id=request.order_id,
        pos_id=request.pos_id,
        store_id=request.store_id,
        ttl_seconds=ttl_seconds,
    )

    return TagsInCartResponse(
        ok=True,
        upserted=upserted,
        ignored_paid=ignored_paid,
        expires_in_seconds=ttl_seconds,
    )


@router.post("/paid", response_model=TagsPaidResponse)
async def register_qr_codes_paid(
    request: TagsPaidRequest,
    _: Annotated[None, Depends(verify_token)],
) -> TagsPaidResponse:
    """Register QR codes from completed payment.

    QR codes in PAID state always pass through the gate.
    PAID state ALWAYS overwrites IN_CART state.
    """
    logger.info(f"Registering {len(request.qr_codes)} paid QR codes for order {request.order_id}")

    # Use config default if ttl_seconds not explicitly provided in request
    config = get_config()
    ttl_seconds = request.ttl_seconds if request.ttl_seconds is not None else config.ttl.paid_seconds

    upserted = await upsert_qr_codes_paid(
        qr_codes=request.qr_codes,
        order_id=request.order_id,
        pos_id=request.pos_id,
        store_id=request.store_id,
        ttl_seconds=ttl_seconds,
    )

    return TagsPaidResponse(
        ok=True,
        upserted=upserted,
        expires_in_seconds=ttl_seconds,
    )


@router.post("/remove", response_model=TagsRemoveResponse)
async def remove_qr_codes_endpoint(
    request: TagsRemoveRequest,
    _: Annotated[None, Depends(verify_token)],
) -> TagsRemoveResponse:
    """Remove QR codes from database.

    Use this endpoint when an order is voided, refunded, or items are removed.
    """
    logger.info(f"Removing {len(request.qr_codes)} QR codes from order {request.order_id}")

    deleted = await remove_qr_codes(qr_codes=request.qr_codes, order_id=request.order_id)

    return TagsRemoveResponse(ok=True, deleted=deleted)


@router.get("/lookup", response_model=TagStatusResponse)
async def lookup_tag_status(
    _: Annotated[None, Depends(verify_token)],
    qr_code: Optional[str] = Query(None, description="QR code to lookup"),
    epc: Optional[str] = Query(None, description="EPC to decode and lookup"),
) -> TagStatusResponse:
    """Look up status by QR code or EPC.

    Provide either qr_code OR epc parameter:
    - qr_code: Direct lookup in database
    - epc: Decoded to QR code first, then looked up

    Returns QR state, order information, and remaining TTL.
    """
    if not qr_code and not epc:
        raise HTTPException(status_code=400, detail="Provide either qr_code or epc parameter")

    # Determine the QR code to look up
    lookup_qr = qr_code
    original_epc = epc

    if epc and not qr_code:
        # Decode EPC to QR code
        lookup_qr = decode_epc(epc)
        logger.debug(f"Decoded EPC {epc} → QR {lookup_qr}")

    if not lookup_qr:
        return TagStatusResponse(qr_code="", epc=original_epc, present=False)

    qr_data = await get_qr_state(lookup_qr)

    if qr_data is None:
        return TagStatusResponse(qr_code=lookup_qr, epc=original_epc, present=False)

    now = int(time.time())
    ttl_remaining = max(0, qr_data["expires_at"] - now)

    return TagStatusResponse(
        qr_code=lookup_qr,
        epc=original_epc,
        present=True,
        state=TagState(qr_data["state"]),
        order_id=qr_data.get("order_id"),
        pos_id=qr_data.get("pos_id"),
        ttl_remaining_seconds=ttl_remaining,
    )

