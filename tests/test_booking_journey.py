from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.channels.whatsapp import AmbiguousDeliveryError
from app.models.base import get_db
from app.workers.inbound import process_event


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


def _payload(message_id: str, wa_id: str, message: dict[str, object]) -> dict[str, object]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"wa_id": wa_id, "profile": {"name": f"Patient {wa_id[-2:]}"}}
                            ],
                            "messages": [{"id": message_id, "from": wa_id, **message}],
                        }
                    }
                ]
            }
        ]
    }


async def _process(message_id: str, wa_id: str, message: dict[str, object]) -> None:
    await process_event(
        {
            "tenant_id": "journey-tenant",
            "message_id": message_id,
            "payload": json.dumps(_payload(message_id, wa_id, message)),
        }
    )


async def test_interactive_booking_is_committed_before_success_and_patient_scoped() -> None:
    db = get_db()
    await db["tenants"].insert_one(
        {
            "_id": "journey-tenant",
            "name": "Journey Clinic",
            "timezone": "Asia/Kolkata",
            "status": "active",
        }
    )
    await db["practitioners"].insert_one(
        {"_id": "journey-doctor", "tenant_id": "journey-tenant", "name": "Dr Journey"}
    )
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    start_local = (local_now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    start = start_local.astimezone(UTC).replace(tzinfo=None)
    await db["slots"].insert_one(
        {
            "_id": "journey-slot",
            "tenant_id": "journey-tenant",
            "practitioner_id": "journey-doctor",
            "start": start,
            "end": start + timedelta(minutes=30),
            "status": "open",
        }
    )

    patient = "919111111111"
    await _process(
        "journey-message-1",
        patient,
        {"type": "text", "text": {"body": "I want to book an appointment tomorrow"}},
    )
    conversation = await db["conversations"].find_one(
        {"tenant_id": "journey-tenant"}
    )
    assert conversation["booking_flow"]["stage"] == "choose_slot"
    assert conversation["booking_flow"]["practitioner_id"] == "journey-doctor"
    assert conversation["booking_flow"]["service"] == "Consultation"

    await _process(
        "journey-message-2",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:journey-slot", "title": "10:00 AM"},
            },
        },
    )
    conversation = await db["conversations"].find_one({"_id": conversation["_id"]})
    assert conversation["booking_flow"]["stage"] == "awaiting_confirmation"
    assert conversation["booking_flow"]["slot_id"] == "journey-slot"
    assert await db["bookings"].count_documents({"tenant_id": "journey-tenant"}) == 0

    await _process(
        "journey-message-3",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking = await db["bookings"].find_one({"tenant_id": "journey-tenant"})
    assert booking["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "journey-slot"}))["status"] == "booked"

    await _process(
        "journey-message-4",
        patient,
        {
            "type": "button",
            "button": {"payload": "booking:confirm", "text": "Confirm"},
        },
    )
    assert await db["bookings"].count_documents({"tenant_id": "journey-tenant"}) == 1

    await db["slots"].insert_one(
        {
            "_id": "journey-slot-2",
            "tenant_id": "journey-tenant",
            "practitioner_id": "journey-doctor",
            "start": start + timedelta(minutes=30),
            "end": start + timedelta(minutes=60),
            "status": "open",
        }
    )
    await _process(
        "journey-reschedule-1",
        patient,
        {"type": "text", "text": {"body": "reschedule my appointment tomorrow"}},
    )
    await _process(
        "journey-reschedule-2",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:journey-slot-2", "title": "10:30 AM"},
            },
        },
    )
    await _process(
        "journey-reschedule-3",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking = await db["bookings"].find_one({"_id": booking["_id"]})
    assert booking["status"] == "rescheduled"
    assert booking["slot_id"] == "journey-slot-2"
    assert (await db["slots"].find_one({"_id": "journey-slot"}))["status"] == "open"
    assert (await db["slots"].find_one({"_id": "journey-slot-2"}))["status"] == "booked"

    await _process(
        "journey-message-other",
        "919222222222",
        {"type": "text", "text": {"body": "cancel my appointment"}},
    )
    assert (await db["bookings"].find_one({"_id": booking["_id"]}))["status"] == "rescheduled"

    await _process(
        "journey-message-5",
        patient,
        {"type": "text", "text": {"body": "cancel my appointment"}},
    )
    await _process(
        "journey-message-5-confirm",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"},
            },
        },
    )
    assert (await db["bookings"].find_one({"_id": booking["_id"]}))["status"] == "cancelled"
    assert (await db["slots"].find_one({"_id": "journey-slot-2"}))["status"] == "open"


async def test_taken_slot_returns_to_a_fresh_picker_without_false_success() -> None:
    db = get_db()
    tenant_id = "journey-tenant"
    await db["tenants"].insert_one(
        {"_id": tenant_id, "name": "Journey Clinic", "timezone": "Asia/Kolkata"}
    )
    await db["practitioners"].insert_one(
        {"_id": "journey-doctor", "tenant_id": tenant_id, "name": "Dr Journey"}
    )
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    start = (local_now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).astimezone(
        UTC
    ).replace(tzinfo=None)
    for index in (1, 2):
        await db["slots"].insert_one(
            {
                "_id": f"recovery-slot-{index}",
                "tenant_id": tenant_id,
                "practitioner_id": "journey-doctor",
                "start": start + timedelta(minutes=30 * (index - 1)),
                "end": start + timedelta(minutes=30 * index),
                "status": "open",
            }
        )
    patient = "919333333333"
    await _process(
        "recovery-message-1",
        patient,
        {"type": "text", "text": {"body": "book an appointment tomorrow"}},
    )
    await _process(
        "recovery-message-2",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:recovery-slot-1", "title": "10:00 AM"},
            },
        },
    )
    await db["slots"].update_one(
        {"_id": "recovery-slot-1"},
        {"$set": {"status": "booked", "booking_id": "another-booking"}},
    )
    await _process(
        "recovery-message-3",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )

    conversation = await db["conversations"].find_one({"tenant_id": tenant_id})
    assert conversation["booking_flow"]["stage"] == "choose_slot"
    assert conversation["booking_flow"]["slots"] == {
        "recovery-slot-2": conversation["booking_flow"]["slots"]["recovery-slot-2"]
    }
    assert await db["bookings"].count_documents(
        {"tenant_id": tenant_id, "contact_id": conversation["contact_id"]}
    ) == 0
    recovery_messages = await db["messages"].count_documents(
        {"tenant_id": tenant_id, "operation_key": {"$regex": "^booking-recovery:"}}
    )
    assert recovery_messages == 1
    assert await db["messages"].count_documents(
        {"tenant_id": tenant_id, "text": {"$regex": "appointment is booked"}}
    ) == 0


async def test_confirmation_send_retry_reuses_the_same_operation_key() -> None:
    db = get_db()
    tenant_id = "journey-tenant"
    await db["tenants"].insert_one(
        {"_id": tenant_id, "name": "Journey Clinic", "timezone": "Asia/Kolkata"}
    )
    await db["practitioners"].insert_one(
        {"_id": "journey-doctor", "tenant_id": tenant_id, "name": "Dr Journey"}
    )
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    start = (local_now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).astimezone(
        UTC
    ).replace(tzinfo=None)
    await db["slots"].insert_one(
        {
            "_id": "retry-slot",
            "tenant_id": tenant_id,
            "practitioner_id": "journey-doctor",
            "start": start,
            "end": start + timedelta(minutes=30),
            "status": "open",
        }
    )
    patient = "919444444444"
    await _process(
        "retry-message-1",
        patient,
        {"type": "text", "text": {"body": "book an appointment tomorrow"}},
    )
    await _process(
        "retry-message-2",
        patient,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:retry-slot", "title": "10:00 AM"},
            },
        },
    )
    confirm = {
        "type": "interactive",
        "interactive": {
            "type": "button_reply",
            "button_reply": {"id": "booking:confirm", "title": "Confirm"},
        },
    }
    operation_keys: list[str] = []

    async def flaky_send(
        tenant_id: str,
        wa_id: str,
        text: str,
        *,
        operation_key: str,
    ) -> dict[str, object]:
        operation_keys.append(operation_key)
        if len(operation_keys) == 1:
            raise AmbiguousDeliveryError("synthetic ambiguous send")
        return {"messages": [{"id": "wamid-recovered"}]}

    from unittest.mock import patch

    with patch("app.workers.inbound.send_freeform", side_effect=flaky_send):
        with pytest.raises(AmbiguousDeliveryError):
            await _process("retry-message-3", patient, confirm)
        conversation = await db["conversations"].find_one({"tenant_id": tenant_id})
        assert conversation["booking_flow"]["stage"] == "awaiting_confirmation"
        await _process("retry-message-3", patient, confirm)

    assert len(set(operation_keys)) == 1
    assert operation_keys[0].startswith("booking-result:")
    assert await db["bookings"].count_documents({"tenant_id": tenant_id}) == 1
    assert await db["messages"].count_documents(
        {"tenant_id": tenant_id, "operation_key": operation_keys[0]}
    ) == 1
