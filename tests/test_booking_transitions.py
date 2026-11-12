from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.booking.engine import cancel_booking, create_booking, move_booking
from app.models.base import get_db
from app.models.collections import Bookings, Slots


async def test_create_is_owned_and_idempotent() -> None:
    tenant_id = "t_booking"
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(tenant_id).insert_one({"_id": "slot-create", "start": future, "status": "open"})

    first = await create_booking(
        tenant_id, "slot-create", "contact-1", "Cleaning", "request-1"
    )
    repeated = await create_booking(
        tenant_id, "slot-create", "contact-1", "Cleaning", "request-1"
    )

    assert first is not None
    assert repeated is not None
    assert repeated["_id"] == first["_id"]
    assert await Bookings(tenant_id).count_documents({}) == 1
    slot = await Slots(tenant_id).find_one({"_id": "slot-create"})
    assert slot is not None
    assert str(slot["booking_id"]) == first["_id"]


async def test_cancel_rejects_another_patient_and_never_reopens_rebooked_slot() -> None:
    tenant_id = "t_cancel"
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(tenant_id).insert_one({"_id": "slot-cancel", "start": future, "status": "open"})
    booking = await create_booking(
        tenant_id, "slot-cancel", "contact-1", "Cleaning", "cancel-create-request"
    )
    assert booking is not None

    assert await cancel_booking(tenant_id, booking["_id"], contact_id="contact-2") is None
    cancelled = await cancel_booking(tenant_id, booking["_id"], contact_id="contact-1")
    assert cancelled is not None

    await Slots(tenant_id).update_one(
        {"_id": "slot-cancel"},
        {"$set": {"status": "booked", "booking_id": "new-booking"}},
    )
    repeated = await cancel_booking(tenant_id, booking["_id"], contact_id="contact-1")
    assert repeated is not None
    slot = await Slots(tenant_id).find_one({"_id": "slot-cancel"})
    assert slot is not None
    assert slot["status"] == "booked"
    assert slot["booking_id"] == "new-booking"


async def test_move_transfers_slot_ownership_together() -> None:
    tenant_id = "t_move"
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(tenant_id).insert_one({"_id": "old-slot", "start": future, "status": "open"})
    await Slots(tenant_id).insert_one({"_id": "new-slot", "start": future + timedelta(hours=1), "status": "open"})
    booking = await create_booking(
        tenant_id, "old-slot", "contact-1", "Cleaning", "create-request"
    )
    assert booking is not None

    moved = await move_booking(
        tenant_id,
        booking["_id"],
        "new-slot",
        "move-request",
        contact_id="contact-1",
    )
    assert moved is not None

    db = get_db()
    old_slot = await db["slots"].find_one({"tenant_id": tenant_id, "_id": "old-slot"})
    new_slot = await db["slots"].find_one({"tenant_id": tenant_id, "_id": "new-slot"})
    stored = await db["bookings"].find_one({"tenant_id": tenant_id})
    assert old_slot["status"] == "open"
    assert "booking_id" not in old_slot
    assert new_slot["status"] == "booked"
    assert new_slot["booking_id"] == stored["_id"]
    assert stored["slot_id"] == "new-slot"
    assert stored["status"] == "rescheduled"
