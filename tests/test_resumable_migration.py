from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.base import get_db
from bson import ObjectId
from ops.resumable_migration import run_migration


async def test_migration_dry_run_does_not_mutate_data() -> None:
    db = get_db()
    tenant_id = "dryrun-tenant"

    contact_id = ObjectId()
    slot_id = ObjectId()
    booking_id = ObjectId()

    await db["contacts"].insert_one({"_id": contact_id, "tenant_id": tenant_id, "name": "Patient"})
    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "held",
        "hold_owner": "temp-owner",
        "hold_expiry": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
    })
    await db["conversations"].insert_one({
        "_id": ObjectId(),
        "tenant_id": tenant_id,
        "contact_id": str(contact_id),
        "state": "open",
    })
    await db["bookings"].insert_one({
        "_id": booking_id,
        "tenant_id": tenant_id,
        "contact_id": str(contact_id),
        "slot_id": str(slot_id),
        "created_at": "2026-11-09T10:00:00",
    })

    # Capture snapshots before
    before_conv = await db["conversations"].find_one({"tenant_id": tenant_id})
    before_slot = await db["slots"].find_one({"tenant_id": tenant_id})
    before_booking = await db["bookings"].find_one({"tenant_id": tenant_id})

    report = await run_migration(tenant_id=tenant_id, apply=False)

    assert report["mode"] == "dry-run"
    assert report["conversation_states_normalized"] == 1
    assert report["expired_holds_released"] == 1
    assert report["references_normalized"]["conversations.contact_id->contacts"] == 1
    assert report["references_normalized"]["bookings.contact_id->contacts"] == 1
    assert report["references_normalized"]["bookings.slot_id->slots"] == 1
    assert report["timestamps_normalized"]["bookings.created_at"] == 1

    # Ensure no mutation happened
    assert await db["conversations"].find_one({"tenant_id": tenant_id}) == before_conv
    assert await db["slots"].find_one({"tenant_id": tenant_id}) == before_slot
    assert await db["bookings"].find_one({"tenant_id": tenant_id}) == before_booking


async def test_migration_apply_normalizes_states_references_and_timestamps() -> None:
    db = get_db()
    tenant_id = "apply-tenant"

    contact_id = ObjectId()
    slot_id = ObjectId()
    booking_id = ObjectId()

    await db["contacts"].insert_one({"_id": contact_id, "tenant_id": tenant_id, "name": "Alice"})
    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "held",
        "hold_owner": "op-1",
        "hold_expiry": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
    })
    conv_id = ObjectId()
    await db["conversations"].insert_one({
        "_id": conv_id,
        "tenant_id": tenant_id,
        "contact_id": str(contact_id),
        "state": "open",
        "started_at": "2026-11-09T08:30:00Z",
    })
    await db["bookings"].insert_one({
        "_id": booking_id,
        "tenant_id": tenant_id,
        "contact_id": str(contact_id),
        "slot_id": str(slot_id),
        "created_at": "2026-11-09T08:30:00",
    })

    # Apply migration
    report = await run_migration(tenant_id=tenant_id, apply=True)

    assert report["mode"] == "apply"
    assert report["conversation_states_normalized"] == 1
    assert report["expired_holds_released"] == 1

    # Check migrated conversation
    migrated_conv = await db["conversations"].find_one({"_id": conv_id})
    assert migrated_conv is not None
    assert migrated_conv["state"] == "bot"
    assert migrated_conv["contact_id"] == contact_id
    assert isinstance(migrated_conv["started_at"], datetime)

    # Check expired slot
    freed_slot = await db["slots"].find_one({"_id": slot_id})
    assert freed_slot is not None
    assert freed_slot["status"] == "open"
    assert "hold_owner" not in freed_slot
    assert "hold_expiry" not in freed_slot

    # Check migrated booking
    migrated_booking = await db["bookings"].find_one({"_id": booking_id})
    assert migrated_booking is not None
    assert migrated_booking["contact_id"] == contact_id
    assert migrated_booking["slot_id"] == slot_id
    assert isinstance(migrated_booking["created_at"], datetime)


async def test_migration_reports_ambiguous_collisions_and_orphans_without_mutation() -> None:
    db = get_db()
    tenant_id = "hazard-tenant"

    hex_id = "660000000000000000000099"
    # Create two contacts with same hex value, one str and one ObjectId
    await db["contacts"].insert_many([
        {"_id": hex_id, "tenant_id": tenant_id, "name": "String ID Contact"},
        {"_id": ObjectId(hex_id), "tenant_id": tenant_id, "name": "ObjectId Contact"},
    ])

    # Create conversation referencing this ambiguous contact
    conv_id = ObjectId()
    await db["conversations"].insert_one({
        "_id": conv_id,
        "tenant_id": tenant_id,
        "contact_id": hex_id,
        "state": "bot",
    })

    # Create message referencing orphan conversation
    msg_id = "msg-orphan"
    await db["messages"].insert_one({
        "_id": msg_id,
        "tenant_id": tenant_id,
        "conversation_id": "non-existent-conv-id",
        "status": "queued",
    })

    report = await run_migration(tenant_id=tenant_id, apply=True)

    # Ambiguous collision must be reported and reference untouched
    assert len(report["operator_review_required"]["ambiguous_collisions"]) == 1
    ambig = report["operator_review_required"]["ambiguous_collisions"][0]
    assert ambig["reference"] == hex_id
    unchanged_conv = await db["conversations"].find_one({"_id": conv_id})
    assert unchanged_conv["contact_id"] == hex_id

    # Orphan reference must be reported and untouched
    assert len(report["operator_review_required"]["orphan_references"]) == 1
    orphan = report["operator_review_required"]["orphan_references"][0]
    assert orphan["reference"] == "non-existent-conv-id"
    unchanged_msg = await db["messages"].find_one({"_id": msg_id})
    assert unchanged_msg["conversation_id"] == "non-existent-conv-id"
    assert report["operator_review_required"]["stranded_messages"] == 1


async def test_migration_tenant_isolation() -> None:
    db = get_db()
    tenant_a = "tenant-iso-a"
    tenant_b = "tenant-iso-b"

    # Contact in tenant B
    contact_b = ObjectId()
    await db["contacts"].insert_one({"_id": contact_b, "tenant_id": tenant_b, "name": "Tenant B Patient"})

    # Conversation in tenant A referencing tenant B's contact
    conv_a = ObjectId()
    await db["conversations"].insert_one({
        "_id": conv_a,
        "tenant_id": tenant_a,
        "contact_id": str(contact_b),
        "state": "bot",
    })

    # Run migration for tenant A
    report_a = await run_migration(tenant_id=tenant_a, apply=True)

    # Must be treated as orphan because contact is in a different tenant!
    assert len(report_a["operator_review_required"]["orphan_references"]) == 1
    conv_after = await db["conversations"].find_one({"_id": conv_a})
    assert conv_after["contact_id"] == str(contact_b)  # Not converted


async def test_migration_idempotent_and_interruptible() -> None:
    db = get_db()
    tenant_id = "idempotent-tenant"

    contact_id = ObjectId()
    slot_id = ObjectId()

    await db["contacts"].insert_one({"_id": contact_id, "tenant_id": tenant_id})
    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "held",
        "hold_expiry": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
    })
    await db["conversations"].insert_one({
        "_id": ObjectId(),
        "tenant_id": tenant_id,
        "contact_id": str(contact_id),
        "state": "open",
    })

    # Run 1
    report_1 = await run_migration(tenant_id=tenant_id, apply=True)
    assert report_1["conversation_states_normalized"] == 1
    assert report_1["expired_holds_released"] == 1
    assert report_1["references_normalized"]["conversations.contact_id->contacts"] == 1

    snap_conv = await db["conversations"].find_one({"tenant_id": tenant_id})
    snap_slot = await db["slots"].find_one({"tenant_id": tenant_id})

    # Run 2 (rerun on already migrated data)
    report_2 = await run_migration(tenant_id=tenant_id, apply=True)
    assert report_2["conversation_states_normalized"] == 0
    assert report_2["expired_holds_released"] == 0
    assert report_2["references_normalized"]["conversations.contact_id->contacts"] == 0

    assert await db["conversations"].find_one({"tenant_id": tenant_id}) == snap_conv
    assert await db["slots"].find_one({"tenant_id": tenant_id}) == snap_slot
