from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from app.models.base import get_db
from bson import ObjectId
from ops.migration_inventory import build_inventory


async def test_inventory_is_read_only_redacted_and_finds_migration_hazards() -> None:
    db = get_db()
    tenant_id = "inventory-tenant"
    contact_id = ObjectId()
    conversation_id = ObjectId()
    await db["tenants"].insert_one({"_id": tenant_id, "plan": "starter"})
    await db["contacts"].insert_many(
        [
            {"_id": contact_id, "tenant_id": tenant_id, "wa_id": "919000000001"},
            {"tenant_id": tenant_id, "wa_id": "919000000001"},
        ]
    )
    await db["conversations"].insert_many(
        [
            {
                "_id": conversation_id,
                "tenant_id": tenant_id,
                "contact_id": str(contact_id),
                "state": "open",
                "started_at": datetime(2026, 1, 1),
            },
            {
                "tenant_id": tenant_id,
                "contact_id": str(contact_id),
                "state": "bot",
            },
        ]
    )
    await db["messages"].insert_one(
        {
            "tenant_id": tenant_id,
            "conversation_id": "missing-conversation",
            "status": "queued",
            "payload": {"patient_name": "must not leak"},
        }
    )
    await db["slots"].insert_one(
        {"tenant_id": tenant_id, "status": "held", "start": datetime(2026, 1, 2)}
    )
    before = deepcopy(await db["messages"].find_one({"tenant_id": tenant_id}))

    report = await build_inventory()

    assert report["read_only"] is True
    assert report["duplicate_contact_groups"]["wa_id"] >= 1
    assert report["duplicate_active_conversation_groups"] >= 1
    assert report["legacy_open_conversations"] >= 1
    assert report["queued_or_placeholder_messages"] >= 1
    assert report["slot_ownership"]["held_without_owner"] >= 1
    orphan = report["orphan_references"]["messages.conversation_id->conversations"]
    assert orphan["count"] >= 1
    assert orphan["samples"] and "missing-conversation" not in orphan["samples"]
    assert report["reference_types"]["conversations.contact_id->contacts"]["str"] >= 1
    assert report["timestamp_provenance"]["conversations.started_at:naive"] >= 1
    assert "must not leak" not in str(report)
    assert await db["messages"].find_one({"tenant_id": tenant_id}) == before
