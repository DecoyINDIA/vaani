"""Reminder worker (F-11, TRD §5.3) — 24h + 2h booking reminders via utility
templates; reschedule-from-reminder deep flow. 06-engineering-plan Phase 3 item 3.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app import audit
from app.channels.whatsapp import AmbiguousDeliveryError, send_template
from app.models.collections import Bookings, Contacts, Practitioners, Slots, Tenants

logger = logging.getLogger(__name__)


async def run_reminders(*, now: datetime | None = None) -> None:
    """Scan all tenants and send upcoming booking reminders."""
    # 1. Fetch all tenants
    tenants = await Tenants.all()
    
    now = now or datetime.now(UTC).replace(tzinfo=None)
    
    for tenant in tenants:
        tenant_id = str(tenant["_id"])
        bookings_accessor = Bookings(tenant_id)
        slots_accessor = Slots(tenant_id)
        contacts_accessor = Contacts(tenant_id)
        timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
        
        # Query bookings that are confirmed/rescheduled
        bookings_cursor = bookings_accessor.find({"status": {"$in": ["confirmed", "rescheduled"]}})
        
        async for booking in bookings_cursor:
            slot_id = booking.get("slot_id")
            slot = await slots_accessor.find_one({"_id": slot_id})
            if (
                not slot
                or slot.get("status") != "booked"
                or slot.get("booking_id") != booking.get("_id")
            ):
                continue
                
            start_time = slot.get("start")
            if not start_time:
                continue
                
            time_diff = start_time - now
            
            for reminder, earliest, latest in (("24h", 23, 25), ("2h", 1, 3)):
                if not (
                    timedelta(hours=earliest) <= time_diff <= timedelta(hours=latest)
                ):
                    continue
                contact = await contacts_accessor.find_one({"_id": booking.get("contact_id")})
                if contact and (
                    contact.get("messaging_opt_out")
                    or contact.get("profile", {}).get("messaging_opt_out")
                ):
                    continue
                patient_name = contact.get("name", "Patient") if contact else "Patient"
                if contact:
                    patient_name = str(
                        contact.get("name")
                        or contact.get("profile", {}).get("name")
                        or "Patient"
                    )
                booking_id = str(booking["_id"])
                local_start = start_time.replace(tzinfo=UTC).astimezone(timezone)
                practitioner = None
                if slot.get("practitioner_id"):
                    practitioner = await Practitioners(tenant_id).find_one(
                        {"_id": slot["practitioner_id"]}
                    )
                doctor_name = str(
                    (practitioner or {}).get("name")
                    or booking.get("practitioner_name")
                    or tenant.get("name")
                    or "Clinic team"
                )
                date_text = local_start.strftime("%A, %d %B %Y")
                time_text = local_start.strftime("%I:%M %p")
                landmark = str(
                    tenant.get("landmark_line")
                    or tenant.get("location_pin")
                    or "See your booking confirmation"
                )
                language_code = str(
                    (contact or {}).get("locale")
                    or (contact or {}).get("profile", {}).get("locale")
                    or tenant.get("locale_default")
                    or "en"
                )
                state_path = f"reminder_status.{reminder}"
                claimed = await bookings_accessor.find_one_and_update(
                    {
                        "_id": booking["_id"],
                        "status": {"$in": ["confirmed", "rescheduled"]},
                        f"{state_path}.state": {"$nin": ["sending", "sent", "delivered"]},
                    },
                    {
                        "$set": {
                            state_path: {
                                "state": "sending",
                                "attempted_at": now,
                            }
                        }
                    },
                )
                if not claimed:
                    continue

                logger.info(
                    "Sending %s reminder to %s for booking %s", reminder, patient_name, booking_id
                )
                wa_id = (contact.get("wa_id") or contact.get("phone")) if contact else None
                if not wa_id:
                    await bookings_accessor.update_one(
                        {"_id": booking["_id"]},
                        {"$set": {state_path: {"state": "failed", "reason": "missing_recipient"}}},
                    )
                    continue
                try:
                    variables = (
                        {
                            "patient_name": patient_name,
                            "doctor_name": doctor_name,
                            "date": date_text,
                            "time": time_text,
                        }
                        if reminder == "24h"
                        else {
                            "patient_name": patient_name,
                            "time": time_text,
                            "landmark": landmark,
                        }
                    )
                    result = await send_template(
                        tenant_id=tenant_id,
                        wa_id=wa_id,
                        template=f"reminder_{reminder}",
                        variables=variables,
                        operation_key=f"reminder:{booking_id}:{reminder}",
                        language_code=language_code,
                    )
                except AmbiguousDeliveryError as e:
                    logger.error("Reminder %s delivery is unknown for %s: %s", reminder, wa_id, e)
                    await bookings_accessor.update_one(
                        {"_id": booking["_id"]},
                        {"$set": {state_path: {"state": "unknown", "reason": type(e).__name__}}},
                    )
                    continue
                except Exception as e:
                    logger.error("Failed to send %s reminder to %s: %s", reminder, wa_id, e)
                    await bookings_accessor.update_one(
                        {"_id": booking["_id"]},
                        {"$set": {state_path: {"state": "failed", "reason": type(e).__name__}}},
                    )
                    continue

                await bookings_accessor.update_one(
                    {"_id": booking["_id"]},
                    {
                        "$set": {
                            state_path: {
                                "state": "sent",
                                "provider_message_id": result.get("messages", [{}])[0].get("id"),
                            }
                        }
                    },
                )
                await audit.record(
                    tenant_id,
                    actor="system",
                    event_type="outbound_template",
                    operation_key=f"reminder-record:{booking_id}:{reminder}",
                    payload={
                        "template": f"T_REMINDER_{reminder.upper()}",
                        "patient_name": patient_name,
                        "booking_id": booking_id,
                        "date": date_text,
                        "time": time_text,
                        "language": language_code,
                    },
                )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting reminders worker scan...")
    asyncio.run(run_reminders())
    logger.info("Reminders worker scan completed.")


if __name__ == "__main__":
    main()
