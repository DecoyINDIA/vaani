"""Tool — cancel booking (TRD §3). Frees the slot (status -> open)."""

from __future__ import annotations

import logging
from typing import Any

from app.models.base import get_db

logger = logging.getLogger(__name__)


async def booking_cancel(tenant_id: str, booking_id: str) -> dict[str, Any]:
    """Tool — cancel booking (TRD §3). Frees the slot (status -> open)."""
    db = get_db()
    
    logger.info(f"Attempting to cancel booking {booking_id} for tenant {tenant_id}")
    booking = await db["bookings"].find_one({"_id": booking_id, "tenant_id": tenant_id})
    if not booking:
        # Fallback if id is string or ObjectId representation
        booking = await db["bookings"].find_one({"_id": booking_id})
        if not booking:
            logger.warning(f"Booking {booking_id} not found")
            return {"status": "failed", "reason": "booking_not_found"}

    slot_id = booking.get("slot_id")
    await db["slots"].update_one(
        {"_id": slot_id, "tenant_id": tenant_id},
        {"$set": {"status": "open"}}
    )
    
    await db["bookings"].update_one(
        {"_id": booking_id, "tenant_id": tenant_id},
        {"$set": {"status": "cancelled"}}
    )
    
    return {"status": "success", "booking_id": booking_id}

