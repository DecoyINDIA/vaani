from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.models.base import get_db, mongo_id_candidates
from app.models.collections import Bookings, Conversations, Messages, Slots
from app.workers.inbound import process_event


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


def _wa_payload(wa_id: str, message: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test Patient"}}],
                            "messages": [{"from": wa_id, "id": f"wamid.{wa_id}", **message}],
                        }
                    }
                ]
            }
        ]
    }


async def _setup_booking(tenant_id: str, wa_id: str) -> tuple[str, str]:
    db = get_db()
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Cancel Clinic",
            "timezone": "Asia/Kolkata",
            "status": "active",
        }
    )
    contact_res = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "phone": wa_id,
            "name": "Test Patient",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    contact_id = str(contact_res.inserted_id)

    future_start = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=None)
    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_cancel",
            "start": future_start,
            "end": future_start + timedelta(minutes=30),
            "status": "booked",
        }
    )
    slot_id = str(slot_res.inserted_id)

    booking_res = await Bookings(tenant_id).insert_one(
        {
            "slot_id": slot_id,
            "contact_id": contact_id,
            "service": "Consultation",
            "status": "confirmed",
            "request_id": "req-init-booking",
            "ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    booking_id = str(booking_res.inserted_id)
    await Slots(tenant_id).update_one({"_id": slot_res.inserted_id}, {"$set": {"booking_id": booking_id}})
    return slot_id, booking_id


@pytest.mark.asyncio
async def test_cancel_prompt_and_confirmation_flow() -> None:
    tenant_id = "t_cancel_test"
    wa_id = "919876543211"
    slot_id, booking_id = await _setup_booking(tenant_id, wa_id)

    # (a) "cancel my appointment" -> booking still confirmed, slot still booked, interactive outbound sent
    payload_1 = _wa_payload(wa_id, {"type": "text", "text": {"body": "cancel my appointment"}})
    await process_event({"tenant_id": tenant_id, "message_id": "msg-cancel-1", "payload": json.dumps(payload_1)})

    booking = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking["status"] == "confirmed"
    slot = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot["status"] == "booked"

    conv = await Conversations(tenant_id).find_one({"contact_id": booking["contact_id"]})
    assert conv is not None
    cancel_flow = conv.get("cancel_flow")
    assert cancel_flow is not None
    assert cancel_flow["stage"] == "awaiting_confirmation"
    assert cancel_flow["booking_id"] == booking_id

    # Check interactive message was stored
    outbound = await Messages(tenant_id).find_one({"direction": "outbound", "type": "interactive"})
    assert outbound is not None

    # (b) tap cancel:confirm -> booking cancelled, slot open, confirmation text reply
    payload_2 = _wa_payload(
        wa_id,
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"}},
        },
    )
    await process_event({"tenant_id": tenant_id, "message_id": "msg-cancel-2", "payload": json.dumps(payload_2)})

    booking_after = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking_after["status"] == "cancelled"
    slot_after = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot_after["status"] == "open"

    conv_after = await Conversations(tenant_id).find_one({"_id": conv["_id"]})
    assert conv_after["cancel_flow"]["stage"] == "completed"

    last_msg = await Messages(tenant_id).find_one({"direction": "outbound", "type": "text"}, sort=[("ts", -1)])
    assert last_msg is not None
    assert "has been cancelled" in last_msg["text"]


@pytest.mark.asyncio
async def test_cancel_keep_leaves_booking_unchanged() -> None:
    tenant_id = "t_cancel_keep"
    wa_id = "919876543212"
    slot_id, booking_id = await _setup_booking(tenant_id, wa_id)

    payload_1 = _wa_payload(wa_id, {"type": "text", "text": {"body": "cancel my appointment"}})
    await process_event({"tenant_id": tenant_id, "message_id": "msg-keep-1", "payload": json.dumps(payload_1)})

    # (c) tap cancel:keep -> unchanged, text reply, cancel_flow removed
    payload_2 = _wa_payload(
        wa_id,
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:keep", "title": "Keep appointment"}},
        },
    )
    await process_event({"tenant_id": tenant_id, "message_id": "msg-keep-2", "payload": json.dumps(payload_2)})

    booking = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking["status"] == "confirmed"
    slot = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot["status"] == "booked"

    conv = await Conversations(tenant_id).find_one({"contact_id": booking["contact_id"]})
    assert "cancel_flow" not in conv or conv.get("cancel_flow") is None

    last_msg = await Messages(tenant_id).find_one({"direction": "outbound", "type": "text"}, sort=[("ts", -1)])
    assert last_msg is not None
    assert "appointment is unchanged" in last_msg["text"]


@pytest.mark.asyncio
async def test_cancel_confirm_with_no_flow_is_ignored() -> None:
    tenant_id = "t_cancel_noflow"
    wa_id = "919876543213"
    slot_id, booking_id = await _setup_booking(tenant_id, wa_id)

    # (d) cancel:confirm sent directly without cancel_flow
    payload = _wa_payload(
        wa_id,
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"}},
        },
    )
    await process_event({"tenant_id": tenant_id, "message_id": "msg-noflow", "payload": json.dumps(payload)})

    booking = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking["status"] == "confirmed"
    slot = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot["status"] == "booked"


@pytest.mark.asyncio
async def test_cancel_confirm_expired_31_minutes_later() -> None:
    tenant_id = "t_cancel_exp"
    wa_id = "919876543214"
    slot_id, booking_id = await _setup_booking(tenant_id, wa_id)

    payload_1 = _wa_payload(wa_id, {"type": "text", "text": {"body": "cancel my appointment"}})
    await process_event({"tenant_id": tenant_id, "message_id": "msg-exp-1", "payload": json.dumps(payload_1)})

    # Backdate cancel_flow created_at by 31 minutes
    db = get_db()
    expired_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=31)
    await db["conversations"].update_one(
        {"tenant_id": tenant_id},
        {"$set": {"cancel_flow.created_at": expired_time}},
    )

    # (e) cancel:confirm 31 min later -> not cancelled, unchanged text reply
    payload_2 = _wa_payload(
        wa_id,
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"}},
        },
    )
    await process_event({"tenant_id": tenant_id, "message_id": "msg-exp-2", "payload": json.dumps(payload_2)})

    booking = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking["status"] == "confirmed"
    slot = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot["status"] == "booked"

    conv = await Conversations(tenant_id).find_one({"tenant_id": tenant_id})
    assert "cancel_flow" not in conv or conv.get("cancel_flow") is None


@pytest.mark.asyncio
async def test_duplicate_cancel_confirm_idempotency() -> None:
    tenant_id = "t_cancel_dup"
    wa_id = "919876543215"
    slot_id, booking_id = await _setup_booking(tenant_id, wa_id)

    payload_1 = _wa_payload(wa_id, {"type": "text", "text": {"body": "cancel my appointment"}})
    await process_event({"tenant_id": tenant_id, "message_id": "msg-dup-1", "payload": json.dumps(payload_1)})

    # (f) First cancel:confirm
    payload_2 = _wa_payload(
        wa_id,
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"}},
        },
    )
    await process_event({"tenant_id": tenant_id, "message_id": "msg-dup-2", "payload": json.dumps(payload_2)})

    # Duplicate cancel:confirm
    await process_event({"tenant_id": tenant_id, "message_id": "msg-dup-2-retry", "payload": json.dumps(payload_2)})

    booking = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking["status"] == "cancelled"
    slot = await Slots(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(slot_id)}})
    assert slot["status"] == "open"
