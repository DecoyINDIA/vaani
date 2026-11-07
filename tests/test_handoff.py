from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.agent.nodes.handoff import handoff
from app.agent.templates import get_template
from app.agent.tools.escalate import escalate
from app.models.base import get_db
from app.owner_api.routes import (
    ReturnPayload,
    StaffReplyPayload,
    reply_to_conversation,
    return_conversation,
    takeover_conversation,
)
from app.workers.escalations import run_escalation_slas
from app.workers.inbound import process_event


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


def _payload(message_id: str, text: str) -> str:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"wa_id": "919111111111", "profile": {"name": "Asha"}}
                                ],
                                "messages": [
                                    {
                                        "id": message_id,
                                        "from": "919111111111",
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )


async def test_handoff_preserves_medical_refusal_after_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    async def after_hours_escalation(*args: object, **kwargs: object) -> dict[str, str]:
        return {"patient_message": get_template("handoff_after_hours", "en")}

    monkeypatch.setattr("app.agent.nodes.handoff.escalate", after_hours_escalation)
    refusal = get_template("medical_refusal", "en")

    result = await handoff(
        {
            "tenant_id": "medical-safety",
            "conversation_id": "medical-safety-conversation",
            "intent": "medical_question",
            "lang": "en",
            "response": refusal,
        }
    )

    assert result["response"] == refusal


async def test_human_request_alerts_once_silences_bot_and_returns_with_summary() -> None:
    db = get_db()
    tenant_id = "handoff-tenant"
    await db["tenants"].insert_one({"_id": tenant_id, "name": "Handoff Clinic"})
    await db["users"].insert_one(
        {
            "_id": "handoff-owner",
            "tenant_id": tenant_id,
            "role": "owner",
            "status": "active",
            "wa_id": "919999999999",
        }
    )

    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "handoff-message-1",
            "payload": _payload("handoff-message-1", "I want to talk to a human"),
        }
    )
    conversation = await db["conversations"].find_one({"tenant_id": tenant_id})
    assert conversation["state"] == "human"
    escalation = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert escalation["status"] == "open"
    assert escalation["notification_status"] == "sent"
    assert await db["escalations"].count_documents({"tenant_id": tenant_id}) == 1
    assert await db["messages"].count_documents(
        {"tenant_id": tenant_id, "direction": "outbound"}
    ) == 1

    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "handoff-message-2",
            "payload": _payload("handoff-message-2", "Are you there?"),
        }
    )
    assert await db["messages"].count_documents(
        {"tenant_id": tenant_id, "direction": "outbound"}
    ) == 1
    assert await db["escalations"].count_documents({"tenant_id": tenant_id}) == 1

    conversation_id = str(conversation["_id"])
    returned = await return_conversation(
        conversation_id,
        ReturnPayload(summary="Staff confirmed the appointment details."),
        tenant_id,
    )
    assert returned["state"] == "bot"
    assert (await db["escalations"].find_one({"tenant_id": tenant_id}))["status"] == "resolved"
    assert (await db["conversations"].find_one({"_id": conversation["_id"]}))["state"] == "bot"


async def test_takeover_matches_generated_object_id() -> None:
    db = get_db()
    inserted = await db["conversations"].insert_one(
        {"tenant_id": "handoff-objectid", "state": "bot", "contact_id": "contact"}
    )
    result = await takeover_conversation(str(inserted.inserted_id), "handoff-objectid")
    assert result["state"] == "human"
    assert (await db["conversations"].find_one({"_id": inserted.inserted_id}))["state"] == "human"


async def test_staff_reply_requires_takeover_and_is_replay_safe() -> None:
    db = get_db()
    tenant_id = "staff-reply"
    contact = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": "919111111111",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    conversation = await db["conversations"].insert_one(
        {
            "tenant_id": tenant_id,
            "state": "bot",
            "contact_id": str(contact.inserted_id),
        }
    )
    conversation_id = str(conversation.inserted_id)
    payload = StaffReplyPayload(text="Your appointment is confirmed.", request_id="reply-1")

    with pytest.raises(Exception) as exc_info:
        await reply_to_conversation(conversation_id, payload, tenant_id)
    assert getattr(exc_info.value, "status_code", None) == 409

    await takeover_conversation(conversation_id, tenant_id)
    sent = await reply_to_conversation(conversation_id, payload, tenant_id)
    repeated = await reply_to_conversation(conversation_id, payload, tenant_id)

    assert sent == {"status": "sent", "deduplicated": False}
    assert repeated == {"status": "sent", "deduplicated": True}
    assert await db["outbound_intents"].count_documents(
        {"tenant_id": tenant_id, "operation_key": "staff-reply:reply-1"}
    ) == 1
    assert await db["messages"].count_documents(
        {"tenant_id": tenant_id, "staff_request_id": "reply-1"}
    ) == 1


async def test_in_hours_sla_notifies_owner_once_after_ten_minutes() -> None:
    db = get_db()
    tenant_id = "handoff-sla"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "timezone": "Asia/Kolkata",
            "dashboard_url": "https://dashboard.example.test",
            "business_hours": [{"day": "monday", "start": "09:00", "end": "18:00"}],
        }
    )
    await db["contacts"].insert_one(
        {
            "_id": "sla-contact",
            "tenant_id": tenant_id,
            "wa_id": "919111111111",
            "name": "Asha",
        }
    )
    await db["conversations"].insert_one(
        {
            "_id": "sla-conversation",
            "tenant_id": tenant_id,
            "contact_id": "sla-contact",
            "state": "bot",
        }
    )
    await db["users"].insert_many(
        [
            {
                "_id": "sla-staff",
                "tenant_id": tenant_id,
                "role": "staff",
                "status": "active",
                "wa_id": "919222222222",
            },
            {
                "_id": "sla-owner",
                "tenant_id": tenant_id,
                "role": "owner",
                "status": "active",
                "wa_id": "919333333333",
            },
        ]
    )
    monday_10_ist = datetime(2026, 11, 9, 4, 30, tzinfo=UTC)

    await escalate(
        tenant_id,
        "sla-conversation",
        "Patient requested staff",
        now=monday_10_ist,
    )
    escalation = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert escalation["sla_mode"] == "in_hours"
    assert escalation["sla_due_at"] == datetime(2026, 11, 9, 4, 40)

    await run_escalation_slas(now=monday_10_ist.replace(minute=41))
    await run_escalation_slas(now=monday_10_ist.replace(minute=42))

    escalation = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert escalation["owner_notification_status"] == "sent"
    assert await db["outbound_intents"].count_documents(
        {"tenant_id": tenant_id, "operation_key": {"$regex": "^escalation-sla:"}}
    ) == 1


async def test_out_of_hours_handoff_queues_until_next_opening() -> None:
    db = get_db()
    tenant_id = "handoff-after-hours"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "timezone": "Asia/Kolkata",
            "business_hours": [{"day": "monday", "start": "09:00", "end": "18:00"}],
        }
    )
    await db["conversations"].insert_one(
        {"_id": "after-hours-conversation", "tenant_id": tenant_id, "state": "bot"}
    )
    sunday_noon_ist = datetime(2026, 11, 8, 6, 30, tzinfo=UTC)

    result = await escalate(
        tenant_id,
        "after-hours-conversation",
        "Patient requested staff",
        lang="hi-Latn",
        now=sunday_noon_ist,
    )

    escalation = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert escalation["sla_mode"] == "out_of_hours"
    assert escalation["sla_due_at"] == datetime(2026, 11, 9, 3, 30)
    assert "agle opening time" in result["patient_message"]
