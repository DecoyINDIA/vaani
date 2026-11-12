"""Regression tests for generated ObjectId boundaries (R03, WP02).

Proves that:
1. Real generated MongoDB ObjectIds are serialized to strings at API/tool boundaries.
2. Single-entity detail reads, list, takeover, reply, return, create, cancel, and move succeed on generated ObjectIds.
3. Legacy string IDs continue to function cleanly.
4. Ambiguous collisions (same hex string existing as both string _id and ObjectId _id) fail with 409 Conflict / ValueError.
5. Cross-tenant access with valid ObjectIds fails closed with 404 Not Found.
6. Payment link creation and webhook reconciliation resolve booking/contact ObjectIds safely.
7. Reminder scans resolve ObjectId references between bookings, slots, and contacts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.agent.tools.payment_link_create import payment_link_create
from app.booking.engine import cancel_booking, create_booking
from app.main import app
from app.models.base import get_db
from app.models.collections import (
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    Messages,
    Payments,
    Slots,
    Tenants,
    Users,
)
from app.owner_api.auth import create_access_token
from app.workers.reminders import _scan_reminders
from bson import ObjectId
from fastapi.testclient import TestClient

TENANT_A = "t_alpha"
TENANT_B = "t_beta"


@pytest.fixture(autouse=True)
async def setup_tenants() -> None:
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    await Tenants.find_by_id(TENANT_A)  # trigger init
    await db["tenants"].insert_one({
        "_id": TENANT_A,
        "name": "Alpha Clinic",
        "wa_number": "919999999001",
        "timezone": "Asia/Kolkata",
    })
    await db["tenants"].insert_one({
        "_id": TENANT_B,
        "name": "Beta Clinic",
        "wa_number": "919999999002",
        "timezone": "Asia/Kolkata",
    })
    await Users(TENANT_A).insert_one({
        "_id": "u_owner_a",
        "role": "owner",
        "status": "active",
        "phone": "919999999001",
    })
    await Users(TENANT_B).insert_one({
        "_id": "u_owner_b",
        "role": "owner",
        "status": "active",
        "phone": "919999999002",
    })


def _auth_headers(tenant_id: str, user_id: str) -> dict[str, str]:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_conversation_generated_objectid_lifecycle() -> None:
    conv_id = ObjectId()
    contact_id = ObjectId()
    await Contacts(TENANT_A).insert_one({
        "_id": contact_id,
        "phone": "919876543210",
        "wa_id": "919876543210",
        "name": "Test Patient",
    })
    await Conversations(TENANT_A).insert_one({
        "_id": conv_id,
        "contact_id": contact_id,
        "state": "bot",
        "last_msg_at": datetime.now(UTC).replace(tzinfo=None),
    })
    await Messages(TENANT_A).insert_one({
        "_id": "msg-1",
        "conversation_id": str(conv_id),
        "direction": "inbound",
        "text": "Hello",
        "ts": datetime.now(UTC).replace(tzinfo=None),
    })
    await Escalations(TENANT_A).insert_one({
        "_id": ObjectId(),
        "conversation_id": conv_id,
        "status": "open",
        "reason": "explicit_request",
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    })

    client = TestClient(app)
    headers_a = _auth_headers(TENANT_A, "u_owner_a")
    headers_b = _auth_headers(TENANT_B, "u_owner_b")

    # 1. List conversations: _id serialized as hex string
    resp = client.get("/api/conversations", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["_id"] == str(conv_id)
    assert items[0]["contact_id"] == str(contact_id)

    # 2. Detail conversation read: 200 for tenant A, 404 for tenant B (cross-tenant denial)
    resp = client.get(f"/api/conversations/{conv_id}", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["_id"] == str(conv_id)

    resp_cross = client.get(f"/api/conversations/{conv_id}", headers=headers_b)
    assert resp_cross.status_code == 404

    # 3. List messages for conversation: 200 with messages for tenant A, empty list for tenant B (non-disclosure)
    resp_msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_a)
    assert resp_msgs.status_code == 200
    assert len(resp_msgs.json()) == 1
    assert resp_msgs.json()[0]["conversation_id"] == str(conv_id)

    resp_msgs_cross = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_b)
    assert resp_msgs_cross.status_code == 200
    assert resp_msgs_cross.json() == []

    # 4. Takeover conversation: 200 for tenant A, 404 for tenant B
    resp_takeover_cross = client.post(f"/api/conversations/{conv_id}/takeover", headers=headers_b)
    assert resp_takeover_cross.status_code == 404

    resp_takeover = client.post(f"/api/conversations/{conv_id}/takeover", headers=headers_a)
    assert resp_takeover.status_code == 200
    assert resp_takeover.json()["state"] == "human"

    convo = await Conversations(TENANT_A).find_one({"_id": conv_id})
    assert convo["state"] == "human"

    # 5. Staff reply
    with patch("app.owner_api.routes.send_freeform", AsyncMock(return_value={"messages": [{"id": "wamid.123"}]})) as mock_send:
        resp_reply = client.post(
            f"/api/conversations/{conv_id}/reply",
            headers=headers_a,
            json={"text": "I can help with that", "request_id": "req-reply-1"},
        )
        assert resp_reply.status_code == 200
        assert resp_reply.json()["status"] == "sent"
        assert mock_send.call_count == 1

    stored_msg = await Messages(TENANT_A).find_one({"staff_request_id": "req-reply-1"})
    assert stored_msg is not None
    assert stored_msg["conversation_id"] == str(conv_id)

    # 6. Return conversation
    resp_return = client.post(
        f"/api/conversations/{conv_id}/return",
        headers=headers_a,
        json={"summary": "Patient problem resolved"},
    )
    assert resp_return.status_code == 200
    assert resp_return.json()["state"] == "bot"

    convo_after = await Conversations(TENANT_A).find_one({"_id": conv_id})
    assert convo_after["state"] == "bot"
    escalation = await Escalations(TENANT_A).find_one({"conversation_id": {"$in": [conv_id, str(conv_id)]}})
    assert escalation["status"] == "resolved"


@pytest.mark.asyncio
async def test_booking_generated_objectid_lifecycle() -> None:
    slot_id = ObjectId()
    contact_id = ObjectId()
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(TENANT_A).insert_one({"_id": slot_id, "start": future, "status": "open"})
    await Contacts(TENANT_A).insert_one({
        "_id": contact_id,
        "phone": "919876543210",
        "name": "Booking Patient",
    })

    client = TestClient(app)
    headers_a = _auth_headers(TENANT_A, "u_owner_a")
    headers_b = _auth_headers(TENANT_B, "u_owner_b")

    # 1. Create booking with stringified ObjectIds
    resp_create = client.post(
        "/api/bookings",
        headers=headers_a,
        json={
            "slot_id": str(slot_id),
            "contact_id": str(contact_id),
            "service": "Consultation",
            "request_id": "req-booking-create-1",
        },
    )
    assert resp_create.status_code == 200
    booking_data = resp_create.json()
    booking_id = booking_data["_id"]
    assert isinstance(booking_id, str)
    assert booking_data["status"] == "confirmed"

    persisted_slot = await Slots(TENANT_A).find_one({"_id": slot_id})
    assert persisted_slot["status"] == "booked"
    assert persisted_slot["booking_id"] == ObjectId(booking_id)

    # 2. List bookings: returns serialized booking
    resp_list = client.get("/api/bookings", headers=headers_a)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) == 1
    assert resp_list.json()[0]["_id"] == booking_id

    # 3. Detail booking read
    resp_detail = client.get(f"/api/bookings/{booking_id}", headers=headers_a)
    assert resp_detail.status_code == 200
    assert resp_detail.json()["_id"] == booking_id

    # Cross-tenant read denied
    resp_detail_cross = client.get(f"/api/bookings/{booking_id}", headers=headers_b)
    assert resp_detail_cross.status_code == 404

    # 4. Reschedule to new generated ObjectId slot
    new_slot_id = ObjectId()
    await Slots(TENANT_A).insert_one({"_id": new_slot_id, "start": future + timedelta(hours=1), "status": "open"})

    # Cross-tenant reschedule denied
    resp_move_cross = client.patch(
        f"/api/bookings/{booking_id}",
        headers=headers_b,
        json={
            "status": "rescheduled",
            "new_slot_id": str(new_slot_id),
            "request_id": "req-move-cross",
        },
    )
    assert resp_move_cross.status_code in (404, 409)

    resp_move = client.patch(
        f"/api/bookings/{booking_id}",
        headers=headers_a,
        json={
            "status": "rescheduled",
            "new_slot_id": str(new_slot_id),
            "request_id": "req-move-valid",
        },
    )
    assert resp_move.status_code == 200
    assert resp_move.json()["status"] == "success"

    old_slot = await Slots(TENANT_A).find_one({"_id": slot_id})
    assert old_slot["status"] == "open"
    assert "booking_id" not in old_slot

    new_slot = await Slots(TENANT_A).find_one({"_id": new_slot_id})
    assert new_slot["status"] == "booked"
    assert new_slot["booking_id"] == ObjectId(booking_id)

    # 5. Cancel booking
    resp_cancel_cross = client.patch(
        f"/api/bookings/{booking_id}",
        headers=headers_b,
        json={"status": "cancelled"},
    )
    assert resp_cancel_cross.status_code == 404

    resp_cancel = client.patch(
        f"/api/bookings/{booking_id}",
        headers=headers_a,
        json={"status": "cancelled"},
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "success"

    new_slot_freed = await Slots(TENANT_A).find_one({"_id": new_slot_id})
    assert new_slot_freed["status"] == "open"
    assert "booking_id" not in new_slot_freed

    # Repeating cancel is idempotent and safe
    resp_cancel_repeat = client.patch(
        f"/api/bookings/{booking_id}",
        headers=headers_a,
        json={"status": "cancelled"},
    )
    assert resp_cancel_repeat.status_code == 200


@pytest.mark.asyncio
async def test_ambiguous_id_collision_fails_controlled() -> None:
    # Seed both a string ID and an ObjectId ID with the exact same 24-hex value
    hex_id = "507f1f77bcf86cd799439011"
    oid = ObjectId(hex_id)

    await get_db()["conversations"].insert_one({
        "_id": hex_id,
        "tenant_id": TENANT_A,
        "state": "bot",
    })
    await get_db()["conversations"].insert_one({
        "_id": oid,
        "tenant_id": TENANT_A,
        "state": "human",
    })

    client = TestClient(app)
    headers = _auth_headers(TENANT_A, "u_owner_a")

    resp = client.get(f"/api/conversations/{hex_id}", headers=headers)
    assert resp.status_code == 409
    assert "ambiguous" in resp.json()["detail"].lower()

    resp_takeover = client.post(f"/api/conversations/{hex_id}/takeover", headers=headers)
    assert resp_takeover.status_code == 409


@pytest.mark.asyncio
async def test_legacy_string_ids_continue_to_work() -> None:
    legacy_conv_id = "conv-legacy-001"
    legacy_slot_id = "slot-legacy-001"
    legacy_contact_id = "contact-legacy-001"

    await Contacts(TENANT_A).insert_one({
        "_id": legacy_contact_id,
        "phone": "919876543210",
        "name": "Legacy Patient",
    })
    await Conversations(TENANT_A).insert_one({
        "_id": legacy_conv_id,
        "contact_id": legacy_contact_id,
        "state": "bot",
    })
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(TENANT_A).insert_one({
        "_id": legacy_slot_id,
        "start": future,
        "status": "open",
    })

    client = TestClient(app)
    headers = _auth_headers(TENANT_A, "u_owner_a")

    # Read legacy conversation
    resp = client.get(f"/api/conversations/{legacy_conv_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["_id"] == legacy_conv_id

    # Create and cancel booking on legacy slot
    booking = await create_booking(
        TENANT_A, legacy_slot_id, legacy_contact_id, "Checkup", "req-legacy-book"
    )
    assert booking is not None
    booking_id = booking["_id"]

    cancelled = await cancel_booking(TENANT_A, booking_id, contact_id=legacy_contact_id)
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"

    slot = await Slots(TENANT_A).find_one({"_id": legacy_slot_id})
    assert slot["status"] == "open"


@pytest.mark.asyncio
async def test_payment_and_razorpay_reconciliation_with_generated_objectids() -> None:
    slot_id = ObjectId()
    contact_id = ObjectId()
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await Slots(TENANT_A).insert_one({"_id": slot_id, "start": future, "status": "open"})
    await Contacts(TENANT_A).insert_one({
        "_id": contact_id,
        "phone": "919876543210",
        "wa_id": "919876543210",
        "name": "Payment Patient",
    })
    await get_db()["tenants"].update_one(
        {"_id": TENANT_A},
        {"$set": {"razorpay_account_id": "acc_alpha"}},
    )

    booking = await create_booking(
        TENANT_A, str(slot_id), str(contact_id), "Root Canal", "req-pay-book"
    )
    assert booking is not None
    booking_id = booking["_id"]

    # 1. Create payment link for booking
    link_result = await payment_link_create(
        TENANT_A,
        str(contact_id),
        50000,
        request_id="pay-req-1",
        booking_id=booking_id,
    )
    assert link_result["status"] == "success"
    provider_link_id = link_result["payment_id"]

    payment_record = await Payments.find_by_link_id_unscoped(provider_link_id)
    assert payment_record is not None
    assert payment_record["contact_id"] == str(contact_id)
    assert payment_record["booking_id"] == booking_id

    # 2. Reconcile webhook against active booking
    with patch("app.gateway.razorpay.verify_razorpay_signature", return_value=True):
        payload = {
            "event": "payment_link.paid",
            "account_id": "acc_alpha",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": provider_link_id,
                        "amount": 50000,
                        "currency": "INR",
                        "reference_id": payment_record["reference_id"],
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_123",
                        "status": "captured",
                    }
                },
            },
        }
        client = TestClient(app)
        resp = client.post(
            "/webhooks/razorpay",
            json=payload,
            headers={"X-Razorpay-Signature": "dummy"},
        )
        assert resp.status_code == 200

    updated_payment = await Payments.find_by_link_id_unscoped(provider_link_id)
    assert updated_payment["status"] == "paid"
    assert updated_payment["provider_payment_id"] == "pay_test_123"

    # 3. Test that payment on a cancelled booking flags reconciliation error
    await cancel_booking(TENANT_A, booking_id)

    second_link = await payment_link_create(
        TENANT_A,
        str(contact_id),
        50000,
        request_id="pay-req-2",
        booking_id=booking_id,
    )
    second_link_id = second_link["payment_id"]
    second_record = await Payments.find_by_link_id_unscoped(second_link_id)

    with patch("app.gateway.razorpay.verify_razorpay_signature", return_value=True):
        payload_cancelled = {
            "event": "payment_link.paid",
            "account_id": "acc_alpha",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": second_link_id,
                        "amount": 50000,
                        "currency": "INR",
                        "reference_id": second_record["reference_id"],
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_456",
                        "status": "captured",
                    }
                },
            },
        }
        resp = client.post(
            "/webhooks/razorpay",
            json=payload_cancelled,
            headers={"X-Razorpay-Signature": "dummy"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "reconciliation_required"

    reconciled_payment = await Payments.find_by_link_id_unscoped(second_link_id)
    assert "cancelled_booking" in reconciled_payment["reconciliation_errors"]


@pytest.mark.asyncio
async def test_reminders_scan_pairs_generated_objectids() -> None:
    slot_id = ObjectId()
    contact_id = ObjectId()
    now = datetime(2026, 11, 10, 10, 0, 0)
    slot_start = now + timedelta(hours=24)

    await Slots(TENANT_A).insert_one({
        "_id": slot_id,
        "start": slot_start,
        "status": "booked",
        "booking_id": None,  # will be updated
    })
    await Contacts(TENANT_A).insert_one({
        "_id": contact_id,
        "phone": "919876543210",
        "wa_id": "919876543210",
        "name": "Reminder Patient",
    })

    booking_id = ObjectId()
    await Bookings(TENANT_A).insert_one({
        "_id": booking_id,
        "slot_id": slot_id,
        "contact_id": contact_id,
        "status": "confirmed",
        "request_id": "req-rem-book",
        "ts": now,
    })
    await Slots(TENANT_A).update_one({"_id": slot_id}, {"$set": {"booking_id": booking_id}})

    with patch("app.workers.reminders.send_template", AsyncMock(return_value={"messages": [{"id": "wamid.rem"}]})) as mock_send:
        tenant_doc = await Tenants.find_by_id(TENANT_A)
        assert tenant_doc is not None
        await _scan_reminders([tenant_doc], now)
        assert mock_send.call_count == 1

    updated_booking = await Bookings(TENANT_A).find_one({"_id": booking_id})
    assert updated_booking["reminder_status"]["24h"]["state"] == "sent"
