from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.channels.whatsapp import (
    TEMPLATE_CONTRACTS,
    TEMPLATE_LANGUAGES,
    AmbiguousDeliveryError,
    send_freeform,
    send_template,
)
from app.config import settings
from app.models.base import get_db
from app.workers.inbound import process_event
from app.workers.reminders import run_reminders


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


async def _send_inbound(
    tenant_id: str, message_id: str, wa_id: str, message: dict[str, object]
) -> None:
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": message_id,
            "payload": json.dumps(_inbound_payload(message_id, wa_id, message)),
        }
    )


async def test_template_approval_contract_fidelity() -> None:
    """Verifies all registered templates match Meta-approved contracts in ops/whatsapp_templates.md."""
    # 1. Verify contract parameter definitions
    assert TEMPLATE_CONTRACTS["reminder_24h"] == ("patient_name", "doctor_name", "date", "time")
    assert TEMPLATE_CONTRACTS["reminder_2h"] == ("patient_name", "time", "landmark")
    assert TEMPLATE_CONTRACTS["escalation_alert_staff"] == (
        "patient_name",
        "patient_phone",
        "reason",
        "dashboard_url",
    )
    assert TEMPLATE_CONTRACTS["weekly_summary_owner"] == (
        "owner_name",
        "date_range_str",
        "convs_count",
        "confirmed_count",
        "recovered_count",
        "revenue_str",
    )
    assert TEMPLATE_CONTRACTS["missed_call_bridge"] == ("clinic_name",)

    # 2. Verify supported language codes
    assert TEMPLATE_LANGUAGES == {"en", "hi", "hi-Latn", "or"}

    db = get_db()
    tenant_id = "test-template-tenant"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "whatsapp": {"phone_number_id": "sender-test", "access_token_env": "VAANI_TEST_TOKEN"},
        }
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    await db["contacts"].insert_one(
        {"tenant_id": tenant_id, "wa_id": "919876543210", "last_inbound_ts": now}
    )

    # 3. Missing variables reject
    with pytest.raises(ValueError, match="requires variables"):
        await send_template(
            tenant_id,
            "919876543210",
            "reminder_24h",
            {"patient_name": "Test"},  # missing doctor_name, date, time
            operation_key="op-missing-var",
        )

    # 4. Extraneous variables reject
    with pytest.raises(ValueError, match="requires variables"):
        await send_template(
            tenant_id,
            "919876543210",
            "missed_call_bridge",
            {"clinic_name": "Sharma Dental", "extra_var": "bad"},
            operation_key="op-extra-var",
        )

    # 5. Unsupported language code rejects
    with pytest.raises(ValueError, match="Unsupported template language"):
        await send_template(
            tenant_id,
            "919876543210",
            "missed_call_bridge",
            {"clinic_name": "Sharma Dental"},
            operation_key="op-bad-lang",
            language_code="fr",
        )


async def test_two_clinic_routing_across_all_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that 2 clinics route all template types to their own senders and credentials."""
    db = get_db()
    now = datetime.now(UTC).replace(tzinfo=None)

    for tenant_id, sender_id, token_env, wa_id in (
        ("clinic-alpha", "sender-alpha-123", "VAANI_WA_TOKEN_ALPHA", "919000000001"),
        ("clinic-beta", "sender-beta-456", "VAANI_WA_TOKEN_BETA", "919000000002"),
    ):
        await db["tenants"].insert_one(
            {
                "_id": tenant_id,
                "whatsapp": {"phone_number_id": sender_id, "access_token_env": token_env},
            }
        )
        await db["contacts"].insert_one(
            {"tenant_id": tenant_id, "wa_id": wa_id, "last_inbound_ts": now}
        )

    monkeypatch.setenv("VAANI_WA_TOKEN_ALPHA", "secret-token-alpha")
    monkeypatch.setenv("VAANI_WA_TOKEN_BETA", "secret-token-beta")
    monkeypatch.setattr(settings, "use_mock_adapters", False)

    recorded_calls: list[dict[str, Any]] = []

    class MockResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"messages": [{"id": f"wamid-{len(recorded_calls)}"}]}

    class MockClient:
        async def __aenter__(self) -> MockClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> MockResponse:
            recorded_calls.append({"url": url, **kwargs})
            return MockResponse()

    monkeypatch.setattr("app.channels.whatsapp.httpx.AsyncClient", MockClient)

    # Clinic Alpha: 24h reminder (Hindi)
    await send_template(
        "clinic-alpha",
        "919000000001",
        "reminder_24h",
        {
            "patient_name": "Patient Alpha",
            "doctor_name": "Dr. Alpha",
            "date": "Monday, 10 Nov 2026",
            "time": "10:00 AM",
        },
        operation_key="alpha-24h",
        language_code="hi",
    )

    # Clinic Beta: 2h reminder (Odia)
    await send_template(
        "clinic-beta",
        "919000000002",
        "reminder_2h",
        {
            "patient_name": "Patient Beta",
            "time": "02:00 PM",
            "landmark": "Near Main Market",
        },
        operation_key="beta-2h",
        language_code="or",
    )

    # Clinic Alpha: Missed call bridge (Hinglish)
    await send_template(
        "clinic-alpha",
        "919000000001",
        "missed_call_bridge",
        {"clinic_name": "Alpha Dental Care"},
        operation_key="alpha-bridge",
        language_code="hi-Latn",
    )

    # Clinic Beta: Staff alert (English)
    await send_template(
        "clinic-beta",
        "919000000002",
        "escalation_alert_staff",
        {
            "patient_name": "Patient Beta",
            "patient_phone": "919000000002",
            "reason": "medical_question",
            "dashboard_url": "https://dashboard.vaani.app/c/clinic-beta",
        },
        operation_key="beta-staff-alert",
        language_code="en",
    )

    # Clinic Alpha: Weekly summary (English)
    await send_template(
        "clinic-alpha",
        "919000000001",
        "weekly_summary_owner",
        {
            "owner_name": "Dr. Alpha",
            "date_range_str": "02 Nov - 08 Nov 2026",
            "convs_count": "45",
            "confirmed_count": "30",
            "recovered_count": "8",
            "revenue_str": "Rs 15,000",
        },
        operation_key="alpha-summary",
        language_code="en",
    )

    # Assertions
    assert len(recorded_calls) == 5
    # Alpha calls routed to sender-alpha-123 with secret-token-alpha
    for idx in [0, 2, 4]:
        assert recorded_calls[idx]["url"] == "https://graph.facebook.com/v20.0/sender-alpha-123/messages"
        assert recorded_calls[idx]["headers"]["Authorization"] == "Bearer secret-token-alpha"

    # Beta calls routed to sender-beta-456 with secret-token-beta
    for idx in [1, 3]:
        assert recorded_calls[idx]["url"] == "https://graph.facebook.com/v20.0/sender-beta-456/messages"
        assert recorded_calls[idx]["headers"]["Authorization"] == "Bearer secret-token-beta"


async def test_two_clinic_interactive_booking_journey_and_isolation() -> None:
    """Verifies 2 clinics can run concurrent bookings, status checks, cancels, moves with tenant isolation."""
    db = get_db()
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    start_1 = local_now.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)
    start_2 = local_now.replace(hour=11, minute=0, second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)

    for clinic_id, clinic_name, doc_id, doc_name in (
        ("clinic-a", "Clinic Alpha", "doc-a", "Dr. Alice"),
        ("clinic-b", "Clinic Beta", "doc-b", "Dr. Bob"),
    ):
        await db["tenants"].insert_one(
            {
                "_id": clinic_id,
                "name": clinic_name,
                "timezone": "Asia/Kolkata",
                "status": "active",
            }
        )
        await db["practitioners"].insert_one(
            {"_id": doc_id, "tenant_id": clinic_id, "name": doc_name}
        )
        await db["slots"].insert_one(
            {
                "_id": f"slot-{clinic_id}-1",
                "tenant_id": clinic_id,
                "practitioner_id": doc_id,
                "start": start_1,
                "end": start_1 + timedelta(minutes=30),
                "status": "open",
            }
        )
        await db["slots"].insert_one(
            {
                "_id": f"slot-{clinic_id}-2",
                "tenant_id": clinic_id,
                "practitioner_id": doc_id,
                "start": start_2,
                "end": start_2 + timedelta(minutes=30),
                "status": "open",
            }
        )

    patient_a = "919000000001"
    patient_b = "919000000002"

    # Step 1: Patient A books at Clinic A
    await _send_inbound(
        "clinic-a", "msg-a-1", patient_a, {"type": "text", "text": {"body": "I want to book an appointment today"}}
    )
    await _send_inbound(
        "clinic-a",
        "msg-a-2",
        patient_a,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:slot-clinic-a-1", "title": "10:00 AM"},
            },
        },
    )
    await _send_inbound(
        "clinic-a",
        "msg-a-3",
        patient_a,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking_a = await db["bookings"].find_one({"tenant_id": "clinic-a"})
    assert booking_a is not None
    assert booking_a["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "slot-clinic-a-1"}))["status"] == "booked"

    # Step 2: Patient B books at Clinic B
    await _send_inbound(
        "clinic-b", "msg-b-1", patient_b, {"type": "text", "text": {"body": "book appointment today"}}
    )
    await _send_inbound(
        "clinic-b",
        "msg-b-2",
        patient_b,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:slot-clinic-b-1", "title": "10:00 AM"},
            },
        },
    )
    await _send_inbound(
        "clinic-b",
        "msg-b-3",
        patient_b,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking_b = await db["bookings"].find_one({"tenant_id": "clinic-b"})
    assert booking_b is not None
    assert booking_b["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "slot-clinic-b-1"}))["status"] == "booked"

    # Step 3: Status checks
    await _send_inbound(
        "clinic-a", "msg-a-status", patient_a, {"type": "text", "text": {"body": "what is the status of my booking"}}
    )
    last_msg_a = await db["messages"].find_one(
        {"tenant_id": "clinic-a", "direction": "outbound"}, sort=[("ts", -1)]
    )
    assert last_msg_a is not None
    assert "confirmed" in last_msg_a["text"]

    await _send_inbound(
        "clinic-b", "msg-b-status", patient_b, {"type": "text", "text": {"body": "what is the status of my booking"}}
    )
    last_msg_b = await db["messages"].find_one(
        {"tenant_id": "clinic-b", "direction": "outbound"}, sort=[("ts", -1)]
    )
    assert last_msg_b is not None
    assert "confirmed" in last_msg_b["text"]

    # Step 4: Cross-clinic negative check
    # Patient A messages Clinic B attempting to cancel: Clinic B must not touch Patient B's booking
    await _send_inbound(
        "clinic-b", "msg-cross-cancel", patient_a, {"type": "text", "text": {"body": "cancel my appointment"}}
    )
    booking_b_check = await db["bookings"].find_one({"_id": booking_b["_id"]})
    assert booking_b_check["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "slot-clinic-b-1"}))["status"] == "booked"

    # Step 5: Cross-patient negative check
    # Patient X (unrelated) messages Clinic A attempting to cancel Patient A's booking
    await _send_inbound(
        "clinic-a", "msg-x-cancel", "919000000099", {"type": "text", "text": {"body": "cancel my appointment"}}
    )
    booking_a_check = await db["bookings"].find_one({"_id": booking_a["_id"]})
    assert booking_a_check["status"] == "confirmed"
    assert (await db["slots"].find_one({"_id": "slot-clinic-a-1"}))["status"] == "booked"

    # Step 6: Patient A reschedules at Clinic A
    await _send_inbound(
        "clinic-a", "msg-a-resched-1", patient_a, {"type": "text", "text": {"body": "reschedule my appointment today"}}
    )
    await _send_inbound(
        "clinic-a",
        "msg-a-resched-2",
        patient_a,
        {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "slot:slot-clinic-a-2", "title": "11:00 AM"},
            },
        },
    )
    await _send_inbound(
        "clinic-a",
        "msg-a-resched-3",
        patient_a,
        {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "booking:confirm", "title": "Confirm"},
            },
        },
    )
    booking_a_resched = await db["bookings"].find_one({"_id": booking_a["_id"]})
    assert booking_a_resched["status"] == "rescheduled"
    assert booking_a_resched["slot_id"] == "slot-clinic-a-2"
    assert (await db["slots"].find_one({"_id": "slot-clinic-a-1"}))["status"] == "open"
    assert (await db["slots"].find_one({"_id": "slot-clinic-a-2"}))["status"] == "booked"

    # Step 7: Patient A cancels at Clinic A
    await _send_inbound(
        "clinic-a", "msg-a-cancel", patient_a, {"type": "text", "text": {"body": "cancel my appointment"}}
    )
    booking_a_cancelled = await db["bookings"].find_one({"_id": booking_a["_id"]})
    assert booking_a_cancelled["status"] == "cancelled"
    assert (await db["slots"].find_one({"_id": "slot-clinic-a-2"}))["status"] == "open"


async def test_two_clinic_opt_out_stop_and_resubscribe_start() -> None:
    """Verifies that STOP unsubscribes the contact from reminders and START re-subscribes."""
    db = get_db()
    for clinic_id in ("clinic-opt-a", "clinic-opt-b"):
        await db["tenants"].insert_one(
            {
                "_id": clinic_id,
                "name": clinic_id,
                "timezone": "Asia/Kolkata",
                "status": "active",
            }
        )

    patient_a = "919888800001"
    patient_b = "919888800002"

    # Patient A sends STOP to clinic-opt-a
    await _send_inbound(
        "clinic-opt-a", "msg-stop", patient_a, {"type": "text", "text": {"body": "STOP"}}
    )

    contact_a = await db["contacts"].find_one({"tenant_id": "clinic-opt-a", "wa_id": patient_a})
    assert contact_a is not None
    assert contact_a.get("messaging_opt_out") is True
    assert contact_a.get("opt_out_at") is not None

    # Patient B at clinic-opt-b is unaffected
    contact_b = await db["contacts"].find_one({"tenant_id": "clinic-opt-b", "wa_id": patient_b})
    assert contact_b is None  # no opt out recorded for B

    # Setup slots and bookings 24 hours in the future
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    target_start = (local_now + timedelta(hours=24)).replace(second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)

    await db["slots"].insert_one(
        {
            "_id": "slot-opt-a",
            "tenant_id": "clinic-opt-a",
            "practitioner_id": "doc-1",
            "start": target_start,
            "end": target_start + timedelta(minutes=30),
            "status": "booked",
        }
    )
    await db["bookings"].insert_one(
        {
            "_id": "bk-opt-a",
            "tenant_id": "clinic-opt-a",
            "contact_id": str(contact_a["_id"]),
            "slot_id": "slot-opt-a",
            "status": "confirmed",
            "practitioner_name": "Dr. Opt",
        }
    )

    # Run reminder scan for clinic-opt-a: Patient A must be skipped because they opted out
    await run_reminders(now=datetime.now(UTC))
    assert (
        await db["outbound_intents"].count_documents(
            {"tenant_id": "clinic-opt-a", "operation_key": {"$regex": "^reminder:"}}
        )
        == 0
    )

    # Patient A sends START to clinic-opt-a to opt back in
    await _send_inbound(
        "clinic-opt-a", "msg-start", patient_a, {"type": "text", "text": {"body": "START"}}
    )
    contact_a_resub = await db["contacts"].find_one({"_id": contact_a["_id"]})
    assert contact_a_resub.get("messaging_opt_out") is False
    assert "opt_out_at" not in contact_a_resub


async def test_two_clinic_provider_failure_and_unknown_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that provider HTTP 500 records failed state and timeouts record unknown without blind retry."""
    db = get_db()
    tenant_id = "clinic-failure-test"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "whatsapp": {"phone_number_id": "sender-fail", "access_token_env": "VAANI_FAIL_TOKEN"},
        }
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    await db["contacts"].insert_one(
        {"tenant_id": tenant_id, "wa_id": "919777700001", "last_inbound_ts": now}
    )
    monkeypatch.setenv("VAANI_FAIL_TOKEN", "token-fail")
    monkeypatch.setattr(settings, "use_mock_adapters", False)

    # 1. Provider returns HTTP 500 -> OutboundIntent state is 'failed'
    class Error500Response:
        status_code = 500

    class Error500Client:
        async def __aenter__(self) -> Error500Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Error500Response:
            return Error500Response()

    monkeypatch.setattr("app.channels.whatsapp.httpx.AsyncClient", Error500Client)

    with pytest.raises(RuntimeError, match="WhatsApp API error 500"):
        await send_freeform(
            tenant_id, "919777700001", "Hello 500", operation_key="op-fail-500"
        )

    intent_failed = await db["outbound_intents"].find_one({"operation_key": "op-fail-500"})
    assert intent_failed is not None
    assert intent_failed["state"] == "failed"
    assert intent_failed["last_error"] == "HTTP 500"

    # 2. Provider network timeout -> OutboundIntent state is 'unknown', raises AmbiguousDeliveryError
    import httpx

    class TimeoutClient:
        async def __aenter__(self) -> TimeoutClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Any:
            raise httpx.ConnectTimeout("Network timed out")

    monkeypatch.setattr("app.channels.whatsapp.httpx.AsyncClient", TimeoutClient)

    with pytest.raises(AmbiguousDeliveryError, match="provider result is unknown"):
        await send_freeform(
            tenant_id, "919777700001", "Hello Timeout", operation_key="op-timeout"
        )

    intent_unknown = await db["outbound_intents"].find_one({"operation_key": "op-timeout"})
    assert intent_unknown is not None
    assert intent_unknown["state"] == "unknown"

    # Replay of ambiguous send is blocked
    with pytest.raises(AmbiguousDeliveryError, match="delivery state is unknown"):
        await send_freeform(
            tenant_id, "919777700001", "Hello Timeout", operation_key="op-timeout"
        )
