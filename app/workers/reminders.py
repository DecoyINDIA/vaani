"""Reminder worker (F-11, TRD §5.3) — 24h + 2h booking reminders via utility
templates; reschedule-from-reminder deep flow. 06-engineering-plan Phase 3 item 3.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app import audit
from app.models.collections import Bookings, Contacts, Slots, Tenants

logger = logging.getLogger(__name__)


async def run_reminders() -> None:
    """Scan all tenants and send upcoming booking reminders."""
    # 1. Fetch all tenants
    tenants = await Tenants.all()
    
    now = datetime.now(UTC).replace(tzinfo=None)
    
    for tenant in tenants:
        tenant_id = str(tenant["_id"])
        bookings_accessor = Bookings(tenant_id)
        slots_accessor = Slots(tenant_id)
        contacts_accessor = Contacts(tenant_id)
        
        # Query bookings that are confirmed/rescheduled
        bookings_cursor = bookings_accessor.find({"status": {"$in": ["confirmed", "rescheduled"]}})
        
        async for booking in bookings_cursor:
            slot_id = booking.get("slot_id")
            slot = await slots_accessor.find_one({"_id": slot_id})
            if not slot:
                continue
                
            start_time = slot.get("start")
            if not start_time:
                continue
                
            reminders_sent = booking.get("reminders_sent", [])
            time_diff = start_time - now
            
            # Check for 24h reminder (between 23h and 25h in the future)
            if timedelta(hours=23) <= time_diff <= timedelta(hours=25):
                if "24h" not in reminders_sent:
                    contact_id = booking.get("contact_id")
                    contact = await contacts_accessor.find_one({"_id": contact_id})
                    patient_name = contact.get("name", "Patient") if contact else "Patient"
                    
                    logger.info(
                        "Sending 24h reminder to %s for booking %s", patient_name, booking["_id"]
                    )
                    
                    await audit.record(
                        tenant_id,
                        actor="system",
                        event_type="outbound_template",
                        payload={
                            "template": "T_REMINDER_24H",
                            "patient_name": patient_name,
                            "booking_id": str(booking["_id"]),
                            "start": start_time.isoformat()
                        }
                    )
                    
                    if contact:
                        wa_id = contact.get("wa_id") or contact.get("phone")
                        if wa_id:
                            from app.channels.whatsapp import send_template
                            try:
                                await send_template(
                                    tenant_id=tenant_id,
                                    wa_id=wa_id,
                                    template="reminder_24h",
                                    variables={
                                        "patient_name": patient_name,
                                        "booking_id": str(booking["_id"]),
                                        "start": start_time.isoformat()
                                    }
                                )
                            except Exception as e:
                                logger.error(f"Failed to send 24h reminder to {wa_id}: {e}")
                    
                    await bookings_accessor.update_one(
                        {"_id": booking["_id"]},
                        {"$addToSet": {"reminders_sent": "24h"}}
                    )
            
            # Check for 2h reminder (between 1h and 3h in the future)
            elif timedelta(hours=1) <= time_diff <= timedelta(hours=3):
                if "2h" not in reminders_sent:
                    contact_id = booking.get("contact_id")
                    contact = await contacts_accessor.find_one({"_id": contact_id})
                    patient_name = contact.get("name", "Patient") if contact else "Patient"
                    
                    logger.info(
                        "Sending 2h reminder to %s for booking %s", patient_name, booking["_id"]
                    )
                    
                    await audit.record(
                        tenant_id,
                        actor="system",
                        event_type="outbound_template",
                        payload={
                            "template": "T_REMINDER_2H",
                            "patient_name": patient_name,
                            "booking_id": str(booking["_id"]),
                            "start": start_time.isoformat()
                        }
                    )
                    
                    if contact:
                        wa_id = contact.get("wa_id") or contact.get("phone")
                        if wa_id:
                            from app.channels.whatsapp import send_template
                            try:
                                await send_template(
                                    tenant_id=tenant_id,
                                    wa_id=wa_id,
                                    template="reminder_2h",
                                    variables={
                                        "patient_name": patient_name,
                                        "booking_id": str(booking["_id"]),
                                        "start": start_time.isoformat()
                                    }
                                )
                            except Exception as e:
                                logger.error(f"Failed to send 2h reminder to {wa_id}: {e}")
                    
                    await bookings_accessor.update_one(
                        {"_id": booking["_id"]},
                        {"$addToSet": {"reminders_sent": "2h"}}
                    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting reminders worker scan...")
    asyncio.run(run_reminders())
    logger.info("Reminders worker scan completed.")


if __name__ == "__main__":
    main()
