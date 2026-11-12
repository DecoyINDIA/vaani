"""Integration Checkpoint 1 (INT-1) scripted multi-tenant transcript test.

Validates the complete Wave 1 journey across two distinct tenants under mock adapters:
1. FAQ query: replies stripped of internal [source_ref: ...] citation tags.
2. Booking flow: slots_get excludes past slots; hold_slot and booking confirmation work.
3. Status check: renders human-readable local appointment times.
4. Cancellation flow: prompts for explicit button confirmation before cancelling.
5. Unsupported media: non-text inbound (audio) gets a polite text reply.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.config import Settings
from app.main import create_app
from app.models.base import get_db
from app.workers.inbound import process_event

from tests.test_feature_flags import _collect_paths


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


def _inbound_payload(message_id: str, wa_id: str, message: dict[str, object]) -> dict[str, object]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"wa_id": wa_id, "profile": {"name": f"Patient {wa_id[-4:]}"}}
                            ],
                            "messages": [{"id": message_id, "from": wa_id, **message}],
                        }
                    }
                ]
            }
        ]
    }


async def _send(tenant_id: str, message_id: str, wa_id: str, message: dict[str, object]) -> None:
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": message_id,
            "payload": json.dumps(_inbound_payload(message_id, wa_id, message)),
        }
    )


@pytest.mark.asyncio
async def test_wave1_end_to_end_multi_tenant_transcript() -> None:
    db = get_db()
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    now_kolkata = datetime.now(UTC).astimezone(kolkata_tz)
    tomorrow_kolkata = now_kolkata + timedelta(days=1)
    
    # Times in UTC for datastore
    slot_time_apex = tomorrow_kolkata.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)
    slot_time_bright = tomorrow_kolkata.replace(hour=11, minute=0, second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)
    past_slot_time = (now_kolkata - timedelta(hours=2)).astimezone(UTC).replace(tzinfo=None)

    # Seed 2 distinct clinics
    for tenant_id, clinic_name, doc_id, doc_name, slot_time in [
        ("tenant-apex", "Apex Health Care", "doc-apex", "Dr. Anita", slot_time_apex),
        ("tenant-bright", "Bright Smile Clinic", "doc-bright", "Dr. Bimal", slot_time_bright),
    ]:
        await db["tenants"].insert_one({
            "_id": tenant_id,
            "name": clinic_name,
            "timezone": "Asia/Kolkata",
            "status": "active",
            "business_profile": {
                "business_type": "clinic",
                "customer_term": "patient",
                "staff_term": "doctor",
            },
        })
        await db["practitioners"].insert_one({
            "_id": doc_id,
            "tenant_id": tenant_id,
            "name": doc_name,
        })
        # Add future valid slot
        await db["slots"].insert_one({
            "_id": f"slot-{tenant_id}-future",
            "tenant_id": tenant_id,
            "practitioner_id": doc_id,
            "start": slot_time,
            "end": slot_time + timedelta(minutes=30),
            "status": "open",
        })
        # Add past slot that must be excluded by W1-03 guard
        await db["slots"].insert_one({
            "_id": f"slot-{tenant_id}-past",
            "tenant_id": tenant_id,
            "practitioner_id": doc_id,
            "start": past_slot_time,
            "end": past_slot_time + timedelta(minutes=30),
            "status": "open",
        })
        # Seed FAQ knowledge base
        await db["kb_entries"].insert_one({
            "tenant_id": tenant_id,
            "key": "faq_fees",
            "kind": "faq",
            "question": "fee charges consultation",
            "answer": f"Consultation fee at {clinic_name} is Rs 500.",
            "source_ref": "faq_fees",
        })

    patient_apex = "919000000001"
    patient_bright = "919000000002"

    # =========================================================================
    # Tenant Apex Journey
    # =========================================================================

    # 1. FAQ: citation stripped (W1-01)
    await _send(
        "tenant-apex", "msg-apex-1", patient_apex,
        {"type": "text", "text": {"body": "how much is the consultation fee"}},
    )
    last_msg = await db["messages"].find_one(
        {"tenant_id": "tenant-apex", "direction": "outbound"},
        sort=[("ts", -1)],
    )
    assert last_msg is not None
    assert "[source_ref:" not in last_msg["text"]
    assert "Rs 500" in last_msg["text"]

    # 2. Book tomorrow: slots_get presents future slot and no past slot (W1-03)
    await _send(
        "tenant-apex", "msg-apex-2", patient_apex,
        {"type": "text", "text": {"body": "I want to book an appointment tomorrow"}},
    )
    # Pick slot
    await _send(
        "tenant-apex", "msg-apex-3", patient_apex,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:slot-tenant-apex-future", "title": "10:00 AM"},
            },
        },
    )
    # Confirm booking
    await _send(
        "tenant-apex", "msg-apex-4", patient_apex,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking_apex = await db["bookings"].find_one({"tenant_id": "tenant-apex"})
    assert booking_apex is not None
    assert booking_apex["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "slot-tenant-apex-future"}))["status"] == "booked"
    # Verify past slot was never booked
    assert (await db["slots"].find_one({"_id": "slot-tenant-apex-past"}))["status"] == "open"

    # 3. Status check: formatted local time (W1-05)
    await _send(
        "tenant-apex", "msg-apex-5", patient_apex,
        {"type": "text", "text": {"body": "what is the status of my booking"}},
    )
    status_msg = await db["messages"].find_one(
        {"tenant_id": "tenant-apex", "direction": "outbound"},
        sort=[("ts", -1)],
    )
    assert status_msg is not None
    assert "confirmed" in status_msg["text"]
    # Formatted local time: "10:00 AM" in Asia/Kolkata
    assert "10:00 AM" in status_msg["text"]
    assert "T10:00:00" not in status_msg["text"]

    # 4. Cancel confirmation: prompt then button tap (W1-04)
    await _send(
        "tenant-apex", "msg-apex-6", patient_apex,
        {"type": "text", "text": {"body": "cancel my appointment"}},
    )
    booking_still_active = await db["bookings"].find_one({"_id": booking_apex["_id"]})
    assert booking_still_active["status"] == "confirmed"  # Not yet cancelled!

    # Tap cancel:confirm button
    await _send(
        "tenant-apex", "msg-apex-7", patient_apex,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "cancel:confirm", "title": "Yes, cancel"},
            },
        },
    )
    booking_cancelled = await db["bookings"].find_one({"_id": booking_apex["_id"]})
    assert booking_cancelled["status"] == "cancelled"
    assert (await db["slots"].find_one({"_id": "slot-tenant-apex-future"}))["status"] == "open"

    # 5. Unsupported media: polite non-text reply (W1-10)
    await _send(
        "tenant-apex", "msg-apex-8", patient_apex,
        {"type": "audio", "audio": {"id": "audio-recording-123"}},
    )
    media_msg = await db["messages"].find_one(
        {"tenant_id": "tenant-apex", "direction": "outbound"},
        sort=[("ts", -1)],
    )
    assert media_msg is not None
    assert "only read text messages" in media_msg["text"]

    # =========================================================================
    # Tenant Bright Isolation Verification
    # =========================================================================
    # Ensure tenant Bright has zero leakage from tenant Apex
    assert await db["bookings"].count_documents({"tenant_id": "tenant-bright"}) == 0
    assert await db["messages"].count_documents({"tenant_id": "tenant-bright"}) == 0
    assert (await db["slots"].find_one({"_id": "slot-tenant-bright-future"}))["status"] == "open"

    # Patient Bright interacts with Tenant Bright: distinct response, no interference
    await _send(
        "tenant-bright", "msg-bright-1", patient_bright,
        {"type": "text", "text": {"body": "how much is the consultation fee"}},
    )
    bright_msg = await db["messages"].find_one(
        {"tenant_id": "tenant-bright", "direction": "outbound"},
        sort=[("ts", -1)],
    )
    assert bright_msg is not None
    assert "[source_ref:" not in bright_msg["text"]
    assert "Rs 500" in bright_msg["text"]


def test_staging_boot_flags_off_health_and_unmounted_exotel() -> None:
    staging_settings = Settings(
        app_env="staging",
        jwt_secret="x" * 32,
        use_mock_adapters=False,
        use_mock_llm=False,
        meta_app_secret="test-meta-secret",
        meta_webhook_verify_token="test-verify-token",
        openrouter_api_key="test-openrouter-key",
        llm_model_classifier="mock-classifier",
        llm_model_responder="mock-responder",
        llm_model_embedding="mock-embedding",
        enable_voice=False,
        enable_payments=False,
        enable_billing=False,
    )
    # 1. validate_runtime() passes with WhatsApp + LLM alone
    staging_settings.validate_runtime()

    test_app = create_app(staging_settings)
    routes = _collect_paths(test_app)

    # 2. Exotel router is not mounted
    assert not any(p.startswith("/webhooks/exotel") for p in routes)

    # 3. Razorpay router is not mounted
    assert not any(p.startswith("/webhooks/razorpay") for p in routes)

    # 4. Meta webhook is mounted
    assert any(p.startswith("/webhooks/meta") for p in routes)

