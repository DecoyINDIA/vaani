from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.channels.whatsapp import AmbiguousDeliveryError, send_template
from app.config import settings
from app.models.base import get_db
from app.models.collections import Bookings, Contacts, OutboundIntents, Slots
from app.workers.reminders import run_reminders


async def test_operation_key_deduplicates_provider_send() -> None:
    first = await send_template(
        "t_outbound",
        "911111111111",
        "booking_confirm",
        {"name": "Asha"},
        operation_key="booking-confirm:1",
    )
    repeated = await send_template(
        "t_outbound",
        "911111111111",
        "booking_confirm",
        {"name": "Asha"},
        operation_key="booking-confirm:1",
    )
    assert first["mock"] is True
    assert repeated["deduplicated"] is True
    assert await OutboundIntents("t_outbound").count_documents({}) == 1


async def test_ambiguous_send_is_visible_and_not_blindly_retried() -> None:
    old_mock = settings.use_mock_adapters
    old_token = settings.bsp_access_token
    old_phone = settings.bsp_phone_number_id
    settings.use_mock_adapters = False
    settings.bsp_access_token = "synthetic"
    settings.bsp_phone_number_id = "synthetic"
    token_env = "VAANI_WA_TOKEN_UNKNOWN_TEST"
    old_tenant_token = os.environ.get(token_env)
    os.environ[token_env] = "synthetic"
    await get_db()["tenants"].insert_one(
        {
            "_id": "t_unknown",
            "whatsapp": {
                "phone_number_id": "synthetic",
                "access_token_env": token_env,
            },
        }
    )
    post = AsyncMock(side_effect=httpx.ReadTimeout("lost response"))
    try:
        with patch("httpx.AsyncClient.post", post):
            with pytest.raises(AmbiguousDeliveryError):
                await send_template(
                    "t_unknown",
                    "922222222222",
                    "booking_confirm",
                    {"name": "Asha"},
                    operation_key="unknown:1",
                )
            with pytest.raises(AmbiguousDeliveryError):
                await send_template(
                    "t_unknown",
                    "922222222222",
                    "booking_confirm",
                    {"name": "Asha"},
                    operation_key="unknown:1",
                )
        assert post.await_count == 1
        intent = await OutboundIntents("t_unknown").find_one({"operation_key": "unknown:1"})
        assert intent is not None
        assert intent["state"] == "unknown"
    finally:
        settings.use_mock_adapters = old_mock
        settings.bsp_access_token = old_token
        settings.bsp_phone_number_id = old_phone
        if old_tenant_token is None:
            os.environ.pop(token_env, None)
        else:
            os.environ[token_env] = old_tenant_token


async def test_failed_reminder_is_not_recorded_as_sent() -> None:
    tenant_id = "t_reminder_failure"
    now = datetime.now(UTC).replace(tzinfo=None)
    await get_db()["tenants"].insert_one({"_id": tenant_id, "name": "Synthetic Clinic"})
    await Slots(tenant_id).insert_one(
        {
            "_id": "failed-reminder-slot",
            "status": "booked",
            "booking_id": "failed-reminder-booking",
            "start": now + timedelta(hours=24),
        }
    )
    await Bookings(tenant_id).insert_one(
        {
            "_id": "failed-reminder-booking",
            "slot_id": "failed-reminder-slot",
            "contact_id": "failed-reminder-contact",
            "status": "confirmed",
        }
    )
    await Contacts(tenant_id).insert_one(
        {"_id": "failed-reminder-contact", "wa_id": "933333333333", "name": "Asha"}
    )

    with patch(
        "app.workers.reminders.send_template", AsyncMock(side_effect=RuntimeError("provider down"))
    ):
        await run_reminders(now=now)

    booking = await Bookings(tenant_id).find_one({"_id": "failed-reminder-booking"})
    assert booking is not None
    assert booking["reminder_status"]["24h"]["state"] == "failed"


async def test_reminder_uses_approved_contract_and_contact_language() -> None:
    tenant_id = "t_reminder_contract"
    now = datetime(2026, 11, 7, 3, 30)
    await get_db()["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Contract Clinic",
            "timezone": "Asia/Kolkata",
            "landmark_line": "Near Clock Tower",
        }
    )
    await Slots(tenant_id).insert_one(
        {
            "_id": "contract-slot",
            "status": "booked",
            "booking_id": "contract-booking",
            "practitioner_id": "contract-doctor",
            "start": now + timedelta(hours=24),
        }
    )
    await get_db()["practitioners"].insert_one(
        {
            "_id": "contract-doctor",
            "tenant_id": tenant_id,
            "name": "Dr Rao",
        }
    )
    await Bookings(tenant_id).insert_one(
        {
            "_id": "contract-booking",
            "slot_id": "contract-slot",
            "contact_id": "contract-contact",
            "status": "confirmed",
        }
    )
    await Contacts(tenant_id).insert_one(
        {
            "_id": "contract-contact",
            "wa_id": "933333333334",
            "name": "Asha",
            "locale": "or",
        }
    )
    send = AsyncMock(return_value={"messages": [{"id": "wamid-contract"}]})

    with patch("app.workers.reminders.send_template", send):
        await run_reminders(now=now)

    send.assert_awaited_once_with(
        tenant_id=tenant_id,
        wa_id="933333333334",
        template="reminder_24h",
        variables={
            "patient_name": "Asha",
            "doctor_name": "Dr Rao",
            "date": "Sunday, 08 November 2026",
            "time": "09:00 AM",
        },
        operation_key="reminder:contract-booking:24h",
        language_code="or",
    )
