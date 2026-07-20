"""Slot engine (TRD §3, Week 4 task 4.1/4.2).

Schedule expansion: practitioner schedule_template -> concrete `slots` rows via a
nightly job. The holiday calendar blocks generation on closed days (Odisha
festival set seeded at onboarding; owner-editable). Atomic hold/confirm lives with
the booking tools; this module owns generation + closure logic.
"""

from __future__ import annotations

import datetime
import logging
from datetime import date, timedelta
from datetime import datetime as dt
from typing import Any

from app.models.collections import Bookings, Practitioners, Slots, Tenants, Waitlist

logger = logging.getLogger(__name__)


async def expand_schedule(tenant_id: str, practitioner_id: str, horizon_days: int = 30) -> int:
    """Generate open slots for the horizon, skipping holiday_calendar closures."""
    slots_acc = Slots(tenant_id)

    # 1. Load practitioner
    practitioner = await Practitioners(tenant_id).find_one({"_id": practitioner_id})
    if not practitioner:
        return 0

    # 2. Load tenant holiday calendar
    tenant = await Tenants.find_by_id(tenant_id)
    holidays = tenant.get("holiday_calendar", []) if tenant else []
    holidays_str = {str(h) for h in holidays} # "YYYY-MM-DD"
    
    schedule_template = practitioner.get("schedule_template", {})
    if not schedule_template:
        return 0
        
    today = date.today()
    slots_created = 0
    
    weekday_keys = {
        0: "monday",
        1: "tuesday",
        2: "wednesday",
        3: "thursday",
        4: "friday",
        5: "saturday",
        6: "sunday"
    }
    
    for day_offset in range(horizon_days):
        target_date = today + timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")
        
        if date_str in holidays_str:
            continue
            
        weekday_name = weekday_keys[target_date.weekday()]
        day_slots = schedule_template.get(weekday_name, [])
        
        for slot_time in day_slots:
            start_str = slot_time.get("start")
            end_str = slot_time.get("end")
            if not start_str or not end_str:
                continue
                
            try:
                start_h, start_m = map(int, start_str.split(":"))
                end_h, end_m = map(int, end_str.split(":"))
            except ValueError:
                continue
                
            start_dt = dt.combine(target_date, datetime.time(start_h, start_m))
            end_dt = dt.combine(target_date, datetime.time(end_h, end_m))
            
            # Check if slot exists
            existing = await slots_acc.find_one({
                "practitioner_id": practitioner_id,
                "start": start_dt
            })

            if not existing:
                try:
                    await slots_acc.insert_one({
                        "practitioner_id": practitioner_id,
                        "start": start_dt,
                        "end": end_dt,
                        "status": "open",
                        "version": 1
                    })
                    slots_created += 1
                except Exception:
                    # Catch duplicate key errors if index constraint fires under concurrency
                    pass
                    
    return slots_created


async def hold_slot(tenant_id: str, slot_id: str) -> bool:
    """Atomically hold a slot for 120 seconds if open or expired."""
    now = dt.now(datetime.UTC).replace(tzinfo=None)

    query = {
        "_id": slot_id,
        "$or": [
            {"status": "open"},
            {"status": "held", "hold_expiry": {"$lt": now}}
        ]
    }

    update = {
        "$set": {
            "status": "held",
            "hold_expiry": now + timedelta(seconds=120)
        }
    }

    result = await Slots(tenant_id).find_one_and_update(query, update)
    return result is not None


async def confirm_booking(
    tenant_id: str, slot_id: str, contact_id: str, service: str
) -> dict[str, Any] | None:
    """Atomically confirm a held slot and create a booking record."""
    now = dt.now(datetime.UTC).replace(tzinfo=None)

    query = {
        "_id": slot_id,
        "status": "held",
        "hold_expiry": {"$gt": now}
    }

    update = {
        "$set": {
            "status": "booked"
        }
    }

    slot = await Slots(tenant_id).find_one_and_update(query, update)
    if not slot:
        return None

    booking = {
        "slot_id": slot_id,
        "contact_id": contact_id,
        "service": service,
        "status": "confirmed",
        "ts": now
    }

    try:
        await Bookings(tenant_id).insert_one(booking)
    except Exception as e:
        logger.error(f"Failed to insert booking record for slot {slot_id}: {e}")
        # Compensation: rollback the slot status back to "held"
        await Slots(tenant_id).update_one(
            {"_id": slot_id},
            {"$set": {"status": "held"}}
        )
        raise
    return {"tenant_id": tenant_id, **booking}


async def claim_waitlist_slot(tenant_id: str, slot_id: str, contact_id: str, service: str) -> bool:
    """Attempt to atomically hold and confirm a waitlist slot for a patient.
    First tap wins: returns True if successful, False if slot is already booked or held.
    """
    # 1. Try to hold slot
    held = await hold_slot(tenant_id, slot_id)
    if not held:
        return False
        
    # 2. Confirm booking
    booking = await confirm_booking(tenant_id, slot_id, contact_id, service)
    if not booking:
        return False
        
    # 3. Update waitlist entry to fulfilled
    slot = await Slots(tenant_id).find_one({"_id": slot_id})
    if slot:
        practitioner_id = slot.get("practitioner_id")
        slot_date = slot.get("start")
        if practitioner_id and slot_date:
            date_str = slot_date.strftime("%Y-%m-%d")
            await Waitlist(tenant_id).update_one(
                {
                    "contact_id": contact_id,
                    "practitioner_id": practitioner_id,
                    "date": date_str,
                    "status": "active"
                },
                {"$set": {"status": "fulfilled"}}
            )
            
    return True

