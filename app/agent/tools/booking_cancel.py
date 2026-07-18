"""Tool — cancel booking (TRD §3). Frees the slot (status -> open)."""

from __future__ import annotations

import logging
from typing import Any

from app import audit
from app.models.collections import Bookings, Slots, Waitlist

logger = logging.getLogger(__name__)


async def booking_cancel(tenant_id: str, booking_id: str) -> dict[str, Any]:
    """Tool — cancel booking (TRD §3). Frees the slot (status -> open)."""
    bookings = Bookings(tenant_id)
    slots = Slots(tenant_id)

    logger.info(f"Attempting to cancel booking {booking_id} for tenant {tenant_id}")
    booking = await bookings.find_one({"_id": booking_id})
    if not booking:
        logger.warning(f"Booking {booking_id} not found")
        return {"status": "failed", "reason": "booking_not_found"}

    slot_id = booking.get("slot_id")
    slot = await slots.find_one({"_id": slot_id})

    await slots.update_one({"_id": slot_id}, {"$set": {"status": "open"}})
    await bookings.update_one({"_id": booking_id}, {"$set": {"status": "cancelled"}})
    
    # Audit cancellation
    await audit.record(
        tenant_id,
        actor="system",
        event_type="booking_cancelled",
        payload={"booking_id": booking_id, "slot_id": slot_id},
        conversation_id=None
    )

    # F-22: Cancellation auto-backfill from waitlist
    if slot:
        practitioner_id = slot.get("practitioner_id")
        slot_date = slot.get("start")
        if practitioner_id and slot_date:
            date_str = slot_date.strftime("%Y-%m-%d")
            
            # Find active waitlist entries for this practitioner and date
            waitlist_accessor = Waitlist(tenant_id)
            cursor = waitlist_accessor.find({
                "practitioner_id": practitioner_id,
                "date": date_str,
                "status": "active"
            })
            waitlist_entries = await cursor.to_list(length=100)
            
            if waitlist_entries:
                logger.info(f"Found {len(waitlist_entries)} active waitlist entries for backfill.")
                # Send slot offer to all waitlisted patients
                for entry in waitlist_entries:
                    contact_id = entry.get("contact_id")
                    
                    # Log the slot offer event to audit log (T_SLOT_OPEN_OFFER simulation)
                    await audit.record(
                        tenant_id,
                        actor="system",
                        event_type="outbound_template",
                        payload={
                            "template": "T_SLOT_OPEN_OFFER",
                            "contact_id": str(contact_id),
                            "slot_id": str(slot_id),
                            "practitioner_id": str(practitioner_id),
                            "start": slot_date.isoformat()
                        },
                        conversation_id=None
                    )
                    
    return {"status": "success", "booking_id": booking_id}
