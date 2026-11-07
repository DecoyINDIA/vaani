"""Slot engine (TRD §3, Week 4 task 4.1/4.2).

Schedule expansion: practitioner schedule_template -> concrete `slots` rows via a
nightly job. The holiday calendar blocks generation on closed days (Odisha
festival set seeded at onboarding; owner-editable). Atomic hold/confirm lives with
the booking tools; this module owns generation + closure logic.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime as dt
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app import audit
from app.config import settings
from app.models.base import get_db, serialize_mongo
from app.models.collections import Bookings, JobRuns, Practitioners, Slots, Tenants, Waitlist

logger = logging.getLogger(__name__)


async def expand_schedule(
    tenant_id: str, practitioner_id: str, horizon_days: int = 30, *, now: dt | None = None
) -> int:
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
    timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")) if tenant else "Asia/Kolkata")
    
    schedule_template = practitioner.get("schedule_template", {})
    if not schedule_template:
        return 0
        
    now = now or dt.now(datetime.UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.UTC)
    today = now.astimezone(timezone).date()
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
                
            start_dt = (
                dt.combine(target_date, datetime.time(start_h, start_m), tzinfo=timezone)
                .astimezone(datetime.UTC)
                .replace(tzinfo=None)
            )
            end_dt = (
                dt.combine(target_date, datetime.time(end_h, end_m), tzinfo=timezone)
                .astimezone(datetime.UTC)
                .replace(tzinfo=None)
            )
            
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
                except DuplicateKeyError:
                    # Another worker created this deterministic slot concurrently.
                    pass
                    
    return slots_created


async def run_schedule_expansion(
    *, now: dt | None = None, horizon_days: int = 30, tenant_limit: int = 100
) -> dict[str, int]:
    """Extend each tenant once per clinic-local day; duplicate workers safely skip."""
    now = now or dt.now(datetime.UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.UTC)
    tenants = (await Tenants.all())[:tenant_limit]
    stats = {
        "tenants": 0,
        "practitioners": 0,
        "slots_created": 0,
        "skipped": 0,
        "alerts": 0,
        "failed": 0,
    }
    for tenant in tenants:
        tenant_id = str(tenant["_id"])
        timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
        local_date = now.astimezone(timezone).date().isoformat()
        job_id = f"slot-expansion:{tenant_id}:{local_date}"
        jobs = JobRuns(tenant_id)
        try:
            await jobs.insert_one(
                {
                    "_id": job_id,
                    "job": "slot_expansion",
                    "key": local_date,
                    "state": "running",
                    "started_at": now.astimezone(datetime.UTC).replace(tzinfo=None),
                }
            )
        except DuplicateKeyError:
            stats["skipped"] += 1
            continue
        try:
            practitioners = await Practitioners(tenant_id).find({}).to_list(length=100)
            for practitioner in practitioners:
                stats["practitioners"] += 1
                practitioner_id = str(practitioner["_id"])
                stats["slots_created"] += await expand_schedule(
                    tenant_id,
                    practitioner_id,
                    horizon_days=horizon_days,
                    now=now,
                )
                alert_window_start = (
                    now.astimezone(timezone).date()
                    + timedelta(days=max(0, horizon_days - 7))
                )
                alert_start_utc = (
                    dt.combine(alert_window_start, datetime.time.min, tzinfo=timezone)
                    .astimezone(datetime.UTC)
                    .replace(tzinfo=None)
                )
                future_open = await Slots(tenant_id).count_documents(
                    {
                        "practitioner_id": practitioner_id,
                        "status": "open",
                        "start": {"$gte": alert_start_utc},
                    }
                )
                if future_open == 0:
                    stats["alerts"] += 1
                    await audit.record(
                        tenant_id,
                        actor="system",
                        event_type="operational_alert",
                        payload={
                            "kind": "schedule_exhaustion",
                            "practitioner_id": practitioner_id,
                            "local_date": local_date,
                            "horizon_days": horizon_days,
                        },
                    )
                    logger.error(
                        "Schedule exhaustion for tenant %s practitioner %s",
                        tenant_id,
                        practitioner_id,
                    )
            stats["tenants"] += 1
            await jobs.update_one(
                {"_id": job_id}, {"$set": {"state": "completed", "stats": stats.copy()}}
            )
        except Exception as exc:
            stats["failed"] += 1
            error_type = type(exc).__name__
            await jobs.update_one(
                {"_id": job_id},
                {"$set": {"state": "failed", "error_type": error_type}},
            )
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                payload={
                    "kind": "schedule_expansion_failed",
                    "local_date": local_date,
                    "error_type": error_type,
                },
            )
            logger.exception("Schedule expansion failed for tenant %s", tenant_id)
    return stats


@asynccontextmanager
async def _transaction() -> AsyncIterator[Any | None]:
    """Use real transactions in deployed environments; mocks opt out explicitly."""
    if settings.use_mock_adapters:
        yield None
        return
    async with await get_db().client.start_session() as session:
        async with session.start_transaction():
            yield session


def _session(session: Any | None) -> dict[str, Any]:
    return {"session": session} if session is not None else {}


async def _booking_id(tenant_id: str, external_id: str) -> Any | None:
    """Resolve legacy string/generated IDs and fail on an ambiguous collision."""
    candidates: list[Any] = [external_id]
    if ObjectId.is_valid(external_id):
        candidates.append(ObjectId(external_id))
    matches = await Bookings(tenant_id).find({"_id": {"$in": candidates}}).to_list(length=2)
    if len(matches) > 1:
        raise ValueError("ambiguous booking id")
    return matches[0]["_id"] if matches else None


async def hold_slot(tenant_id: str, slot_id: str, operation_id: str) -> bool:
    """Atomically hold a slot for 120 seconds if open or expired."""
    if not operation_id:
        raise ValueError("operation_id is required")
    now = dt.now(datetime.UTC).replace(tzinfo=None)

    query = {
        "_id": slot_id,
        "$or": [
            {"status": "open"},
            {"status": "held", "hold_expiry": {"$lt": now}},
            {"status": "held", "hold_owner": operation_id},
        ]
    }

    update = {
        "$set": {
            "status": "held",
            "hold_expiry": now + timedelta(seconds=120),
            "hold_owner": operation_id,
        }
    }

    result = await Slots(tenant_id).find_one_and_update(query, update)
    return result is not None


async def confirm_booking(
    tenant_id: str, slot_id: str, contact_id: str, service: str, operation_id: str
) -> dict[str, Any] | None:
    """Confirm only this operation's hold and create one idempotent booking."""
    if not operation_id:
        raise ValueError("operation_id is required")
    existing = await Bookings(tenant_id).find_one({"request_id": operation_id})
    if existing:
        return serialize_mongo(existing)

    now = dt.now(datetime.UTC).replace(tzinfo=None)
    booking_id = ObjectId()
    booking = {
        "_id": booking_id,
        "slot_id": slot_id,
        "contact_id": contact_id,
        "service": service,
        "status": "confirmed",
        "request_id": operation_id,
        "ts": now,
    }

    try:
        async with _transaction() as session:
            slot = await Slots(tenant_id).find_one_and_update(
                {
                    "_id": slot_id,
                    "status": "held",
                    "hold_owner": operation_id,
                    "hold_expiry": {"$gt": now},
                },
                {
                    "$set": {"status": "booked", "booking_id": booking_id},
                    "$unset": {"hold_owner": "", "hold_expiry": ""},
                },
                **_session(session),
            )
            if not slot:
                return None
            await Bookings(tenant_id).insert_one(booking, **_session(session))
    except Exception as e:
        logger.error("Failed to confirm booking for slot %s: %s", slot_id, e)
        if settings.use_mock_adapters:
            await Slots(tenant_id).update_one(
                {"_id": slot_id, "booking_id": booking_id},
                {
                    "$set": {
                        "status": "held",
                        "hold_owner": operation_id,
                        "hold_expiry": now + timedelta(seconds=120),
                    },
                    "$unset": {"booking_id": ""},
                },
            )
        raise
    return serialize_mongo({"tenant_id": tenant_id, **booking})


async def create_booking(
    tenant_id: str,
    slot_id: str,
    contact_id: str,
    service: str,
    operation_id: str,
) -> dict[str, Any] | None:
    existing = await Bookings(tenant_id).find_one({"request_id": operation_id})
    if existing:
        return serialize_mongo(existing)
    if not await hold_slot(tenant_id, slot_id, operation_id):
        return None
    return await confirm_booking(tenant_id, slot_id, contact_id, service, operation_id)


async def cancel_booking(
    tenant_id: str, booking_id: str, *, contact_id: str | None = None
) -> dict[str, Any] | None:
    """Cancel once and free only the slot still owned by this booking."""
    stored_id = await _booking_id(tenant_id, booking_id)
    if stored_id is None:
        return None
    query: dict[str, Any] = {"_id": stored_id}
    if contact_id is not None:
        query["contact_id"] = contact_id

    async with _transaction() as session:
        booking = await Bookings(tenant_id).find_one(query, **_session(session))
        if not booking:
            return None
        if booking.get("status") == "cancelled":
            return serialize_mongo(booking)
        if booking.get("status") not in {"confirmed", "rescheduled"}:
            raise ValueError("booking cannot be cancelled from its current state")

        result = await Bookings(tenant_id).update_one(
            {**query, "status": booking["status"]},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": dt.now(datetime.UTC).replace(tzinfo=None),
                }
            },
            **_session(session),
        )
        if result.modified_count != 1:
            raise RuntimeError("booking changed during cancellation")
        await Slots(tenant_id).update_one(
            {"_id": booking["slot_id"], "status": "booked", "booking_id": booking["_id"]},
            {"$set": {"status": "open"}, "$unset": {"booking_id": ""}},
            **_session(session),
        )
        booking["status"] = "cancelled"
        return serialize_mongo(booking)


async def move_booking(
    tenant_id: str,
    booking_id: str,
    new_slot_id: str,
    operation_id: str,
    *,
    contact_id: str | None = None,
) -> dict[str, Any] | None:
    """Move a booking atomically after acquiring an operation-owned hold."""
    stored_id = await _booking_id(tenant_id, booking_id)
    if stored_id is None:
        return None
    if not await hold_slot(tenant_id, new_slot_id, operation_id):
        return None
    query: dict[str, Any] = {"_id": stored_id}
    if contact_id is not None:
        query["contact_id"] = contact_id
    now = dt.now(datetime.UTC).replace(tzinfo=None)

    async with _transaction() as session:
        booking = await Bookings(tenant_id).find_one(query, **_session(session))
        if not booking or booking.get("status") not in {"confirmed", "rescheduled"}:
            return None
        old_slot_id = booking["slot_id"]
        new_slot = await Slots(tenant_id).find_one_and_update(
            {
                "_id": new_slot_id,
                "status": "held",
                "hold_owner": operation_id,
                "hold_expiry": {"$gt": now},
            },
            {
                "$set": {"status": "booked", "booking_id": booking["_id"]},
                "$unset": {"hold_owner": "", "hold_expiry": ""},
            },
            **_session(session),
        )
        if not new_slot:
            return None
        updated = await Bookings(tenant_id).update_one(
            {**query, "status": booking["status"], "slot_id": old_slot_id},
            {
                "$set": {
                    "slot_id": new_slot_id,
                    "status": "rescheduled",
                    "move_request_id": operation_id,
                }
            },
            **_session(session),
        )
        if updated.modified_count != 1:
            raise RuntimeError("booking changed during reschedule")
        await Slots(tenant_id).update_one(
            {"_id": old_slot_id, "status": "booked", "booking_id": booking["_id"]},
            {"$set": {"status": "open"}, "$unset": {"booking_id": ""}},
            **_session(session),
        )
        return {
            "status": "success",
            "booking_id": str(booking["_id"]),
            "old_slot_id": str(old_slot_id),
            "new_slot_id": str(new_slot_id),
        }


async def claim_waitlist_slot(tenant_id: str, slot_id: str, contact_id: str, service: str) -> bool:
    """Attempt to atomically hold and confirm a waitlist slot for a patient.
    First tap wins: returns True if successful, False if slot is already booked or held.
    """
    # 1. Try to hold slot
    operation_id = f"waitlist:{slot_id}:{contact_id}"
    held = await hold_slot(tenant_id, slot_id, operation_id)
    if not held:
        return False
        
    # 2. Confirm booking
    booking = await confirm_booking(tenant_id, slot_id, contact_id, service, operation_id)
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

