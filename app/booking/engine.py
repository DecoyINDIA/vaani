"""Slot engine (TRD §3, Week 4 task 4.1/4.2).

Schedule expansion: practitioner schedule_template -> concrete `slots` rows via a
nightly job. The holiday calendar blocks generation on closed days (Odisha
festival set seeded at onboarding; owner-editable). Atomic hold/confirm lives with
the booking tools; this module owns generation + closure logic.
"""

from __future__ import annotations

import datetime
from datetime import date, datetime as dt, timedelta, timezone
from typing import Any

from app.models.base import get_db


async def expand_schedule(tenant_id: str, practitioner_id: str, horizon_days: int = 30) -> int:
    """Generate open slots for the horizon, skipping holiday_calendar closures."""
    db = get_db()
    
    # 1. Load practitioner
    practitioner = await db["practitioners"].find_one({"_id": practitioner_id, "tenant_id": tenant_id})
    if not practitioner:
        return 0
    
    # 2. Load tenant holiday calendar
    tenant = await db["tenants"].find_one({"_id": tenant_id})
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
            existing = await db["slots"].find_one({
                "tenant_id": tenant_id,
                "practitioner_id": practitioner_id,
                "start": start_dt
            })
            
            if not existing:
                try:
                    await db["slots"].insert_one({
                        "tenant_id": tenant_id,
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
    db = get_db()
    now = dt.now(timezone.utc).replace(tzinfo=None)
    
    query = {
        "_id": slot_id,
        "tenant_id": tenant_id,
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
    
    result = await db["slots"].find_one_and_update(query, update)
    return result is not None


async def confirm_booking(tenant_id: str, slot_id: str, contact_id: str, service: str) -> dict | None:
    """Atomically confirm a held slot and create a booking record."""
    db = get_db()
    now = dt.now(timezone.utc).replace(tzinfo=None)
    
    query = {
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "held",
        "hold_expiry": {"$gt": now}
    }
    
    update = {
        "$set": {
            "status": "booked"
        }
    }
    
    slot = await db["slots"].find_one_and_update(query, update)
    if not slot:
        return None
        
    booking = {
        "tenant_id": tenant_id,
        "slot_id": slot_id,
        "contact_id": contact_id,
        "service": service,
        "status": "confirmed",
        "ts": now
    }
    
    await db["bookings"].insert_one(booking)
    return booking

