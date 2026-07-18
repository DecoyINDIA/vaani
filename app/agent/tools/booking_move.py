"""Tool — reschedule booking (TRD §3). Same atomic hold semantics + date_confirmed
contract as booking_create."""

from __future__ import annotations

import logging
from typing import Any

from app.booking.engine import hold_slot
from app.models.base import get_db

logger = logging.getLogger(__name__)


async def booking_move(
    tenant_id: str, booking_id: str, new_slot_id: str, *, date_confirmed: bool
) -> dict[str, Any]:
    """Tool — reschedule booking (TRD §3). Same atomic hold semantics as booking_create."""
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before move (TRD §4.3)")

    db = get_db()
    
    logger.info(f"Finding booking {booking_id} to reschedule")
    booking = await db["bookings"].find_one({"_id": booking_id, "tenant_id": tenant_id})
    if not booking:
        booking = await db["bookings"].find_one({"_id": booking_id})
        if not booking:
            logger.warning(f"Booking {booking_id} not found")
            return {"status": "failed", "reason": "booking_not_found"}

    old_slot_id = booking.get("slot_id")

    logger.info(f"Attempting to hold new slot {new_slot_id}")
    held = await hold_slot(tenant_id, new_slot_id)
    if not held:
        logger.warning(f"New slot {new_slot_id} is unavailable")
        return {"status": "failed", "reason": "new_slot_unavailable"}

    # Free old slot
    logger.info(f"Releasing old slot {old_slot_id}")
    await db["slots"].update_one(
        {"_id": old_slot_id, "tenant_id": tenant_id},
        {"$set": {"status": "open"}}
    )

    # Confirm new slot
    logger.info(f"Confirming new slot {new_slot_id}")
    await db["slots"].update_one(
        {"_id": new_slot_id, "tenant_id": tenant_id},
        {"$set": {"status": "booked"}}
    )

    # Update booking reference
    await db["bookings"].update_one(
        {"_id": booking_id, "tenant_id": tenant_id},
        {"$set": {"slot_id": new_slot_id, "status": "rescheduled"}}
    )

    return {
        "status": "success",
        "booking_id": booking_id,
        "old_slot_id": old_slot_id,
        "new_slot_id": new_slot_id
    }

