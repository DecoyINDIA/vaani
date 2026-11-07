"""Tool — reschedule booking (TRD §3). Same atomic hold semantics + date_confirmed
contract as booking_create."""

from __future__ import annotations

import logging
from typing import Any

from app.booking.engine import move_booking

logger = logging.getLogger(__name__)


async def booking_move(
    tenant_id: str,
    booking_id: str,
    new_slot_id: str,
    request_id: str,
    *,
    date_confirmed: bool,
    contact_id: str | None = None,
) -> dict[str, Any]:
    """Tool — reschedule booking (TRD §3). Same atomic hold semantics as booking_create."""
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before move (TRD §4.3)")

    result = await move_booking(
        tenant_id,
        booking_id,
        new_slot_id,
        request_id,
        contact_id=contact_id,
    )
    return result or {"status": "failed", "reason": "booking_or_slot_unavailable"}

