from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.agent.tools.escalate import escalate
from app.channels.whatsapp import (
    AmbiguousDeliveryError,
    send_template,
)
from app.config import settings
from app.models.base import get_db
from app.owner_api.routes import (
    ReturnPayload,
    StaffReplyPayload,
    reply_to_conversation,
    return_conversation,
    takeover_conversation,
)
from app.workers.escalations import run_escalation_slas
from app.workers.healthcheck import check as check_heartbeat
from app.workers.inbound import (
    _dead_letter,
    check_queue_age,
    process_event,
)
from fastapi import HTTPException
from ops.onboard_tenant import TenantConfig, apply_config


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


def _inbound_payload(message_id: str, wa_id: str, text: str) -> dict[str, object]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"wa_id": wa_id, "profile": {"name": f"Patient {wa_id[-4:]}"}}
                            ],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": wa_id,
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


async def _send_inbound(tenant_id: str, message_id: str, wa_id: str, text: str) -> None:
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": message_id,
            "payload": json.dumps(_inbound_payload(message_id, wa_id, text)),
        }
    )


async def test_onboarding_rehearsal_and_rolling_horizon_holiday_changes() -> None:
    """1. Rehearses onboarding and rolling horizon/holiday schedule changes."""
    db = get_db()
    tenant_id = "rehearsal-clinic"

    config_data = {
        "tenant_id": tenant_id,
        "name": "Rehearsal Dental Clinic",
        "timezone": "Asia/Kolkata",
        "plan": "starter",
        "locale_default": "hi",
        "wa_number": "919876543210",
        "voice_number": "919876543211",
        "landmark_line": "Near Post Office, Market Road",
        "location_pin": "https://maps.example.test/rehearsal",
        "dashboard_url": "https://dashboard.example.test",
        "gstin": "21ABCDE1234F1Z5",
        "whatsapp": {
            "phone_number_id": "sender-rehearsal-1",
            "access_token_env": "VAANI_TEST_TOKEN",
        },
        "business_hours": [{"day": "monday", "start": "09:00", "end": "17:00"}],
        "holiday_calendar": [],
        "practitioners": [
            {
                "practitioner_id": "p-rehearsal-1",
                "name": "Dr Sen",
                "services": ["Dental Checkup", "Root Canal"],
                "schedule_template": {
                    "monday": [{"start": "10:00", "end": "10:30"}],
                },
            }
        ],
    }
    config = TenantConfig.model_validate(config_data)
    first_apply = await apply_config(config)
    assert first_apply["slots_created"] > 0

    slots = await db["slots"].find({"tenant_id": tenant_id}).to_list(length=100)
    assert len(slots) > 0
    first_slot = slots[0]

    # Insert an active booking on the first slot
    booking_id = "booking-rehearsal-preserve"
    await db["bookings"].insert_one(
        {
            "_id": booking_id,
            "tenant_id": tenant_id,
            "slot_id": first_slot["_id"],
            "contact_id": "cnt_rehearsal",
            "status": "confirmed",
        }
    )

    # Tenant updates holiday calendar to declare the first slot's date a holiday
    tz = ZoneInfo("Asia/Kolkata")
    slot_date_str = first_slot["start"].astimezone(tz).date().isoformat()
    config_data["holiday_calendar"] = [slot_date_str]
    updated_config = TenantConfig.model_validate(config_data)

    second_apply = await apply_config(updated_config)
    # The existing booking must still be preserved
    retained_booking = await db["bookings"].find_one({"_id": booking_id})
    assert retained_booking is not None
    assert retained_booking["status"] == "confirmed"

    # Idempotent re-run created 0 duplicate slots
    assert second_apply["slots_created"] == 0


async def test_human_request_medical_safety_and_llm_failure_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2. Injects human requests, safety triggers, and LLM provider outages."""
    db = get_db()
    tenant_id = "handoff-safety-clinic"

    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Safety Clinic",
            "timezone": "Asia/Kolkata",
            "business_hours": [{"day": "monday", "start": "09:00", "end": "18:00"}],
            "dashboard_url": "https://dashboard.example.test",
        }
    )
    await db["users"].insert_many(
        [
            {
                "_id": "staff-1",
                "tenant_id": tenant_id,
                "role": "staff",
                "status": "active",
                "wa_id": "919000000001",
            },
            {
                "_id": "owner-1",
                "tenant_id": tenant_id,
                "role": "owner",
                "status": "active",
                "wa_id": "919000000002",
            },
        ]
    )

    # A) Human request injection
    wa_id_human = "919888880001"
    await _send_inbound(tenant_id, "msg-human-1", wa_id_human, "can I talk to a human please")

    conv_human = await db["conversations"].find_one({"tenant_id": tenant_id})
    assert conv_human is not None
    assert conv_human["state"] == "human"

    esc_human = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert esc_human is not None
    assert esc_human["status"] == "open"
    assert esc_human["notification_status"] == "sent"

    # Queued-bot silence check: patient sends a second message while conversation is in human state
    outbound_before = await db["messages"].count_documents(
        {"tenant_id": tenant_id, "direction": "outbound"}
    )
    await _send_inbound(tenant_id, "msg-human-2", wa_id_human, "Are you there? Anyone?")
    outbound_after = await db["messages"].count_documents(
        {"tenant_id": tenant_id, "direction": "outbound"}
    )
    assert outbound_after == outbound_before  # Bot remained silent

    # B) Medical safety refusal trigger
    wa_id_med = "919888880002"
    await _send_inbound(
        tenant_id,
        "msg-med-1",
        wa_id_med,
        "my tooth is bleeding severely, which tablet should I take",
    )
    conv_med = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "_id": {"$ne": conv_human["_id"]}}
    )
    assert conv_med is not None
    assert conv_med["state"] == "human"

    med_reply = await db["messages"].find_one(
        {"tenant_id": tenant_id, "conversation_id": str(conv_med["_id"]), "direction": "outbound"}
    )
    assert med_reply is not None
    # Medical refusal template must be communicated
    assert "medical advice" in med_reply["text"].lower() or "diagnose" in med_reply["text"].lower()

    # C) LLM provider outage injection
    wa_id_llm = "919888880003"
    monkeypatch.setattr(
        "app.agent.nodes.intent.query_llm",
        AsyncMock(side_effect=RuntimeError("upstream OpenRouter 502 Bad Gateway")),
    )
    await _send_inbound(tenant_id, "msg-llm-1", wa_id_llm, "What are your services?")
    conv_llm = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "_id": {"$nin": [conv_human["_id"], conv_med["_id"]]}}
    )
    assert conv_llm is not None
    assert conv_llm["state"] == "human"

    esc_llm = await db["escalations"].find_one(
        {"tenant_id": tenant_id, "conversation_id": str(conv_llm["_id"])}
    )
    assert esc_llm is not None
    assert esc_llm["reason"].endswith("llm_unavailable")

    # Operational alert recorded for provider failure
    provider_alert = await db["audit_log"].find_one(
        {"tenant_id": tenant_id, "event_type": "operational_alert", "payload.kind": "provider_failure"}
    )
    assert provider_alert is not None
    assert provider_alert["payload"]["provider"] == "openrouter_llm"


async def test_staff_takeover_reply_resolution_summary_and_return_to_bot() -> None:
    """3. Verifies staff takeover, replay-safe reply, required summary, and return to bot."""
    db = get_db()
    tenant_id = "staff-flow-clinic"

    contact = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": "919777770001",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    conv = await db["conversations"].insert_one(
        {
            "tenant_id": tenant_id,
            "state": "bot",
            "contact_id": str(contact.inserted_id),
        }
    )
    conv_id = str(conv.inserted_id)

    # Takeover conversation
    takeover_res = await takeover_conversation(conv_id, tenant_id)
    assert takeover_res["state"] == "human"

    # Staff reply with request_id
    reply_payload = StaffReplyPayload(
        text="Hello, this is receptionist Priya. How can I assist you?",
        request_id="staff-req-123",
    )
    first_send = await reply_to_conversation(conv_id, reply_payload, tenant_id)
    repeat_send = await reply_to_conversation(conv_id, reply_payload, tenant_id)
    assert first_send["status"] == "sent"
    assert first_send["deduplicated"] is False
    assert repeat_send["status"] == "sent"
    assert repeat_send["deduplicated"] is True

    # Attempt return without summary must fail (HTTP 422)
    with pytest.raises(HTTPException) as exc_info:
        await return_conversation(conv_id, ReturnPayload(summary=""), tenant_id)
    assert exc_info.value.status_code == 422

    # Return with valid resolution summary
    return_res = await return_conversation(
        conv_id,
        ReturnPayload(summary="Patient confirmed tomorrow appointment at 11am with Dr Sen."),
        tenant_id,
    )
    assert return_res["state"] == "bot"

    updated_conv = await db["conversations"].find_one({"_id": conv.inserted_id})
    assert updated_conv["state"] == "bot"


async def test_clock_controlled_staff_sla_and_in_hours_out_of_hours_escalations() -> None:
    """4. Clock-controlled 30s staff delivery, 10-minute in-hours owner SLA, and out-of-hours queue."""
    db = get_db()
    tenant_id = "sla-clinic"

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
            "_id": "cnt_sla_test",
            "tenant_id": tenant_id,
            "wa_id": "919666660001",
            "name": "Meera Patel",
        }
    )
    await db["conversations"].insert_one(
        {
            "_id": "conv_sla_test",
            "tenant_id": tenant_id,
            "contact_id": "cnt_sla_test",
            "state": "bot",
        }
    )
    await db["users"].insert_many(
        [
            {
                "_id": "sla_staff",
                "tenant_id": tenant_id,
                "role": "staff",
                "status": "active",
                "wa_id": "919666660002",
            },
            {
                "_id": "sla_owner",
                "tenant_id": tenant_id,
                "role": "owner",
                "status": "active",
                "wa_id": "919666660003",
            },
        ]
    )

    # A) In-hours escalation at Monday 10:00 AM IST (04:30 UTC)
    monday_10_ist = datetime(2026, 11, 9, 4, 30, tzinfo=UTC)
    await escalate(
        tenant_id,
        "conv_sla_test",
        "Patient requires human assistance",
        now=monday_10_ist,
    )

    esc = await db["escalations"].find_one({"tenant_id": tenant_id})
    assert esc is not None
    assert esc["sla_mode"] == "in_hours"
    assert esc["sla_due_at"] == datetime(2026, 11, 9, 4, 40)  # 10 minutes SLA

    # 5 minutes in (10:05 IST): SLA not yet breached
    await run_escalation_slas(now=monday_10_ist + timedelta(minutes=5))
    esc_5m = await db["escalations"].find_one({"_id": esc["_id"]})
    assert esc_5m.get("owner_notification_status") != "sent"

    # 11 minutes in (10:41 UTC -> wait, 04:41 UTC is 10:11 IST): SLA breached
    await run_escalation_slas(now=monday_10_ist + timedelta(minutes=11))
    esc_breached = await db["escalations"].find_one({"_id": esc["_id"]})
    assert esc_breached["owner_notification_status"] == "sent"

    # Re-run at minute 12: does not duplicate owner alert send
    await run_escalation_slas(now=monday_10_ist + timedelta(minutes=12))
    owner_intents = await db["outbound_intents"].count_documents(
        {"tenant_id": tenant_id, "operation_key": {"$regex": "^escalation-sla:"}}
    )
    assert owner_intents == 1

    # B) Out-of-hours escalation on Sunday 12:00 PM IST (06:30 UTC)
    sunday_noon_ist = datetime(2026, 11, 8, 6, 30, tzinfo=UTC)
    await db["conversations"].insert_one(
        {
            "_id": "conv_ooh_test",
            "tenant_id": tenant_id,
            "contact_id": "cnt_sla_test",
            "state": "bot",
        }
    )
    ooh_res = await escalate(
        tenant_id,
        "conv_ooh_test",
        "After hours inquiry",
        lang="hi-Latn",
        now=sunday_noon_ist,
    )
    esc_ooh = await db["escalations"].find_one({"conversation_id": "conv_ooh_test"})
    assert esc_ooh["sla_mode"] == "out_of_hours"
    assert esc_ooh["sla_due_at"] == datetime(2026, 11, 9, 3, 30)  # Monday 09:00 AM IST
    assert "agle opening time" in ooh_res["patient_message"]


async def test_operational_alerts_delivery_to_configured_destination_zero_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5. Delivers queue-age, dead-letter, unknown-delivery, provider-failure,

    heartbeat, and schedule-exhaustion alerts to configured destination with ZERO PII.
    """
    dispatched_alerts: list[dict[str, Any]] = []
    meta_mode: str = "ok"

    async def mock_post(client: Any, url: str, **kwargs: Any) -> httpx.Response:
        if url == destination_url:
            json_data = kwargs.get("json", {})
            dispatched_alerts.append({"url": url, "body": json_data})
            return httpx.Response(200, json={"ok": True})
        if "graph.facebook.com" in url:
            if meta_mode == "timeout":
                raise httpx.ConnectTimeout("Connection timed out to Meta Graph API")
            if meta_mode == "500":
                return httpx.Response(500, json={"error": {"message": "Internal Server Error"}})
            return httpx.Response(200, json={"messages": [{"id": "mock_wamid_alert"}]})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    destination_url = "https://alerts.example.test/vaani-ops"
    monkeypatch.setattr(settings, "alerts_destination_url", destination_url)

    db = get_db()
    tenant_id = "alert-test-clinic"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "whatsapp": {"phone_number_id": "sender-alert", "access_token_env": "VAANI_TEST_TOKEN"},
            "timezone": "Asia/Kolkata",
            "holiday_calendar": [],
        }
    )

    # 1. Dead-letter alert
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock()
    mock_redis.xack = AsyncMock()
    await _dead_letter(
        mock_redis,
        msg_id="dlq-msg-101",
        fields={"tenant_id": tenant_id, "message_id": "wamid.dlq101"},
        reason="ValueError",
    )

    # 2. Unknown-delivery alert (simulated network timeout in send_template)
    monkeypatch.setattr("app.channels.whatsapp._offline", lambda: False)
    monkeypatch.setattr("os.environ", {"VAANI_TEST_TOKEN": "mock-token"})
    meta_mode = "timeout"
    with pytest.raises(AmbiguousDeliveryError):
        await send_template(
            tenant_id,
            "919999999999",
            "missed_call_bridge",
            {"clinic_name": "Alert Clinic"},
            operation_key="op-alert-timeout",
        )

    # 3. Provider-failure alert (simulated HTTP 500 from provider)
    meta_mode = "500"
    with pytest.raises(RuntimeError, match="WhatsApp API error 500"):
        await send_template(
            tenant_id,
            "919999999999",
            "missed_call_bridge",
            {"clinic_name": "Alert Clinic"},
            operation_key="op-alert-500",
        )

    # 4. Queue-age alert
    mock_queue_redis = AsyncMock()
    # Simulate pending entry from 120 seconds ago
    two_min_ago_ms = int((datetime.now(UTC).timestamp() - 120) * 1000)
    mock_queue_redis.xpending = AsyncMock(
        return_value={"pending": 3, "min": f"{two_min_ago_ms}-0", "max": f"{two_min_ago_ms + 1000}-0"}
    )
    age = await check_queue_age(mock_queue_redis, max_age_seconds=60.0)
    assert age is not None and age >= 120.0
    assert age is not None and age >= 120.0

    # 5. Worker heartbeat alert
    mock_hb_redis = AsyncMock()
    mock_hb_redis.get = AsyncMock(return_value=None)  # Stale/missing heartbeat
    monkeypatch.setattr("app.workers.healthcheck.get_redis", lambda: mock_hb_redis)
    with pytest.raises(SystemExit):
        await check_heartbeat()

    # 6. Schedule exhaustion alert
    from app.booking.engine import run_schedule_expansion

    await db["practitioners"].insert_one(
        {
            "_id": "p_exhausted",
            "tenant_id": tenant_id,
            "schedule_template": {},  # No template -> 0 future slots
        }
    )
    expansion_stats = await run_schedule_expansion()
    assert expansion_stats["alerts"] >= 1

    # Verify all dispatched alerts reached destination_url
    assert len(dispatched_alerts) >= 6
    for item in dispatched_alerts:
        assert item["url"] == destination_url
        body = item["body"]
        assert body["event_type"] == "operational_alert"
        assert "kind" in body
        assert "details" in body
        assert "timestamp" in body

        # Crucial: verify zero PII in alert payload
        details_str = json.dumps(body["details"]).lower()
        assert "919999999999" not in details_str
        assert "patient_name" not in body["details"]
        assert "phone" not in body["details"]
        assert "wa_id" not in body["details"]
        assert "transcript" not in body["details"]

    kinds = {item["body"]["kind"] for item in dispatched_alerts}
    assert "dead_letter" in kinds
    assert "unknown_delivery" in kinds
    assert "provider_failure" in kinds
    assert "queue_age" in kinds
    assert "worker_heartbeat" in kinds
    assert "schedule_exhaustion" in kinds
