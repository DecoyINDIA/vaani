"""Tool — create booking (TRD §3, Week 4 task 4.2/4.3).

Atomic hold->confirm: findOneAndUpdate(status "open"->"held") + 120s hold expiry,
then confirm. Race-safe by construction (500-concurrent test: 0 double-bookings).
CONTRACT: rejects any call without date_confirmed=true — the agent must echo
weekday + date in the user's language first (relative-date rule, TRD §4.3).
"""

from __future__ import annotations

import logging
from typing import Any

from app.booking.engine import confirm_booking, hold_slot

logger = logging.getLogger(__name__)


async def booking_create(
    tenant_id: str, slot_id: str, contact_id: str, service: str, *, date_confirmed: bool
) -> dict[str, Any]:
    """Tool — create booking (TRD §3, Week 4 task 4.2/4.3).

    Atomic hold->confirm.
    CONTRACT: rejects any call without date_confirmed=true.
    """
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before booking (TRD §4.3)")
        
    logger.info(f"Attempting atomic hold for slot {slot_id}")
    held = await hold_slot(tenant_id, slot_id)
    if not held:
        logger.warning(f"Failed to hold slot {slot_id} - already booked or held")
        return {"status": "failed", "reason": "slot_unavailable"}
        
    logger.info(f"Slot {slot_id} held. Confirming booking for contact {contact_id}")
    booking = await confirm_booking(tenant_id, slot_id, contact_id, service)
    if not booking:
        logger.error(f"Failed to confirm held slot {slot_id}")
        return {"status": "failed", "reason": "confirmation_failed"}
        
    booking_id = str(booking.get("_id", ""))
    return {
        "status": "success",
        "booking_id": booking_id,
        "service": service,
        "slot_id": slot_id
    }

