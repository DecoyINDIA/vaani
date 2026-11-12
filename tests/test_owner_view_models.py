from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.main import app
from app.models.base import get_db
from app.owner_api.auth import create_access_token
from bson import ObjectId
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


@pytest.mark.asyncio
async def test_owner_view_models_enrichment_and_cross_tenant_isolation() -> None:
    db = get_db()
    tenant_a = "t_view_a"
    tenant_b = "t_view_b"

    # Setup Tenants
    await db["tenants"].insert_one(
        {"_id": tenant_a, "name": "Clinic Alpha", "timezone": "Asia/Kolkata", "status": "active"}
    )
    await db["tenants"].insert_one(
        {"_id": tenant_b, "name": "Clinic Beta", "timezone": "Asia/Kolkata", "status": "active"}
    )

    # Setup Staff users
    await db["users"].insert_one(
        {"_id": "u_staff_a", "tenant_id": tenant_a, "role": "staff", "status": "active"}
    )
    await db["users"].insert_one(
        {"_id": "u_staff_b", "tenant_id": tenant_b, "role": "staff", "status": "active"}
    )

    # Setup Tenant A entities
    contact_a_id = ObjectId()
    await db["contacts"].insert_one(
        {
            "_id": contact_a_id,
            "tenant_id": tenant_a,
            "name": "Alice Patient",
            "wa_id": "919000000001",
            "phone": "919000000001",
        }
    )

    doc_a_id = "dr_alpha"
    await db["practitioners"].insert_one(
        {"_id": doc_a_id, "tenant_id": tenant_a, "name": "Dr. Alpha"}
    )

    slot_time = datetime(2026, 11, 20, 4, 30, tzinfo=UTC).replace(tzinfo=None)  # 10:00 AM IST
    slot_a_id = ObjectId()
    await db["slots"].insert_one(
        {
            "_id": slot_a_id,
            "tenant_id": tenant_a,
            "practitioner_id": doc_a_id,
            "start": slot_time,
            "end": slot_time + timedelta(minutes=30),
            "status": "booked",
        }
    )

    booking_a_id = ObjectId()
    await db["bookings"].insert_one(
        {
            "_id": booking_a_id,
            "tenant_id": tenant_a,
            "slot_id": str(slot_a_id),
            "contact_id": str(contact_a_id),
            "service": "Consultation",
            "status": "confirmed",
            "ts": slot_time,
        }
    )

    conv_a_id = ObjectId()
    await db["conversations"].insert_one(
        {
            "_id": conv_a_id,
            "tenant_id": tenant_a,
            "contact_id": str(contact_a_id),
            "channel": "wa",
            "state": "bot",
            "started_at": slot_time,
            "last_msg_at": slot_time,
        }
    )

    await db["messages"].insert_one(
        {
            "tenant_id": tenant_a,
            "conversation_id": str(conv_a_id),
            "direction": "inbound",
            "text": "Hello, I would like to confirm my consultation details.",
            "ts": slot_time,
        }
    )

    await db["escalations"].insert_one(
        {
            "tenant_id": tenant_a,
            "conversation_id": str(conv_a_id),
            "status": "open",
        }
    )

    # Setup Tenant B with colliding entity IDs to test cross-tenant negative check!
    # Even if Tenant B has an entity with the same ID, Tenant A must not join Tenant B's data
    colliding_contact_id = "colliding_contact_id"
    await db["contacts"].insert_one(
        {
            "_id": colliding_contact_id,
            "tenant_id": tenant_b,
            "name": "Bob from Beta",
            "phone": "919999999999",
        }
    )
    # A booking in Tenant A that mistakenly points to colliding_contact_id (belonging to B)
    # should yield contact: None in Tenant A's view
    booking_orphan_id = ObjectId()
    await db["bookings"].insert_one(
        {
            "_id": booking_orphan_id,
            "tenant_id": tenant_a,
            "slot_id": "non_existent_slot",
            "contact_id": colliding_contact_id,
            "service": "Orphan Service",
            "status": "confirmed",
            "ts": slot_time,
        }
    )

    # Tenant A empty conversation with no messages
    conv_empty_id = "conv_empty"
    await db["conversations"].insert_one(
        {
            "_id": conv_empty_id,
            "tenant_id": tenant_a,
            "contact_id": "missing_contact",
            "channel": "wa",
            "state": "bot",
            "started_at": slot_time,
        }
    )

    client = TestClient(app)
    token_a = create_access_token(tenant_a, "u_staff_a")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Test GET /api/conversations
    resp_convs = client.get("/api/conversations", headers=headers_a)
    assert resp_convs.status_code == 200
    convs = resp_convs.json()
    assert len(convs) >= 2

    conv_a = next(c for c in convs if c["_id"] == str(conv_a_id))
    assert conv_a["contact"] is not None
    assert conv_a["contact"]["name"] == "Alice Patient"
    assert conv_a["contact"]["phone"] == "919000000001"
    assert "Hello, I would like to confirm" in conv_a["last_message_preview"]
    assert conv_a["open_escalation"] is True
    # ISO-8601 with tenant offset: +05:30
    assert "+05:30" in conv_a["last_msg_at"]

    conv_empty = next(c for c in convs if c["_id"] == conv_empty_id)
    assert conv_empty["contact"] is None
    assert conv_empty["last_message_preview"] == ""
    assert conv_empty["open_escalation"] is False

    # Test GET /api/bookings
    resp_bookings = client.get("/api/bookings", headers=headers_a)
    assert resp_bookings.status_code == 200
    bookings = resp_bookings.json()
    assert len(bookings) >= 2

    bk_a = next(b for b in bookings if b["_id"] == str(booking_a_id))
    assert bk_a["contact"] is not None
    assert bk_a["contact"]["name"] == "Alice Patient"
    assert bk_a["practitioner"] == {"id": "dr_alpha", "name": "Dr. Alpha"}
    assert bk_a["start"] == "2026-11-20T10:00:00+05:30"
    assert bk_a["end"] == "2026-11-20T10:30:00+05:30"

    # Cross-tenant check: bk_orphan must NOT join Tenant B's contact or missing slot
    bk_orphan = next(b for b in bookings if b["_id"] == str(booking_orphan_id))
    assert bk_orphan["contact"] is None
    assert bk_orphan["start"] is None
    assert bk_orphan["end"] is None
    assert bk_orphan["practitioner"] is None
