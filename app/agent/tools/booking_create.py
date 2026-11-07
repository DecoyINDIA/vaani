"""Tool — create booking (TRD §3, Week 4 task 4.2/4.3).

Atomic hold->confirm: findOneAndUpdate(status "open"->"held") + 120s hold expiry,
then confirm. Race-safe by construction (500-concurrent test: 0 double-bookings).
CONTRACT: rejects any call without date_confirmed=true — the agent must echo
weekday + date in the user's language first (relative-date rule, TRD §4.3).
"""

from __future__ import annotations

import logging
from typing import Any

from app.booking.engine import create_booking

logger = logging.getLogger(__name__)


async def booking_create(
    tenant_id: str,
    slot_id: str,
    contact_id: str,
    service: str,
    request_id: str,
    *,
    date_confirmed: bool,
) -> dict[str, Any]:
    """Tool — create booking (TRD §3, Week 4 task 4.2/4.3).

    Atomic hold->confirm.
    CONTRACT: rejects any call without date_confirmed=true.
    """
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before booking (TRD §4.3)")
        
    booking = await create_booking(tenant_id, slot_id, contact_id, service, request_id)
    if not booking:
        return {"status": "failed", "reason": "slot_unavailable"}
        
    booking_id = str(booking.get("_id", ""))
    return {
        "status": "success",
        "booking_id": booking_id,
        "service": service,
        "slot_id": slot_id
    }

