from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.channels.voice.session import VoiceSession
from app.config import settings
from app.gateway.exotel import (
    consume_stream_grant,
    issue_stream_grant,
    verify_exotel_call,
)
from app.main import app
from app.models.base import get_db
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_voice_grants() -> None:
    await get_db()["voice_grants"].delete_many({})


def test_unverified_callback_cannot_mint_stream_grant() -> None:
    response = TestClient(app).post(
        "/webhooks/exotel",
        data={
            "To": "919999999998",
            "From": "919876543210",
            "CallSid": "attacker-selected-call",
        },
    )
    assert response.status_code == 401
    assert "token=" not in response.text


async def test_call_details_contract_is_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Call": {
                    "Sid": "call-verified",
                    "To": "919999999998",
                    "From": "919876543210",
                }
            }

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, **kwargs: Any) -> Response:
            assert url == (
                "https://api.in.exotel.com/v1/Accounts/account-sid/"
                "Calls/call-verified.json"
            )
            assert kwargs["auth"] == ("api-key", "api-token")
            assert kwargs["params"] == {"details": "true"}
            return Response()

    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "exotel_subdomain", "api.in.exotel.com")
    monkeypatch.setattr(settings, "exotel_sid", "account-sid")
    monkeypatch.setattr(settings, "exotel_api_key", "api-key")
    monkeypatch.setattr(settings, "exotel_api_token", "api-token")
    monkeypatch.setattr("app.gateway.exotel.httpx.AsyncClient", Client)

    assert await verify_exotel_call(
        "call-verified",
        expected_to="919999999998",
        expected_from="919876543210",
    )
    assert not await verify_exotel_call(
        "call-verified",
        expected_to="919999999998",
        expected_from="changed-caller",
    )


async def test_stream_grant_is_bound_short_lived_and_one_use() -> None:
    token = await issue_stream_grant(
        "voice-tenant", "call-bound", "919876543210"
    )
    assert token
    assert not await consume_stream_grant(
        "changed-tenant", "call-bound", "919876543210", token
    )
    assert not await consume_stream_grant(
        "voice-tenant", "changed-call", "919876543210", token
    )
    assert not await consume_stream_grant(
        "voice-tenant", "call-bound", "changed-caller", token
    )
    assert await consume_stream_grant(
        "voice-tenant", "call-bound", "919876543210", token
    )
    assert not await consume_stream_grant(
        "voice-tenant", "call-bound", "919876543210", token
    )

    expired = await issue_stream_grant(
        "voice-tenant", "call-expired", "919876543210"
    )
    assert expired
    await get_db()["voice_grants"].update_one(
        {"tenant_id": "voice-tenant", "call_sid": "call-expired"},
        {"$set": {"expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)}},
    )
    assert not await consume_stream_grant(
        "voice-tenant", "call-expired", "919876543210", expired
    )


async def test_caller_consent_and_contacts_are_isolated() -> None:
    db = get_db()
    await db["contacts"].delete_many({"tenant_id": "voice-isolation"})
    await db["conversations"].delete_many({"tenant_id": "voice-isolation"})

    first = VoiceSession("voice-isolation", "call-a", caller_phone="911111111111")
    await first.initialize()
    await first.handle_user_input(b"INIT", lang="en")
    await first.handle_user_input(b"DTMF_1", lang="en")
    assert first.consent_accepted

    second = VoiceSession("voice-isolation", "call-b", caller_phone="922222222222")
    await second.initialize()
    assert not second.consent_accepted
    blocked = await second.handle_user_input(b"spoken audio", lang="en")
    assert blocked["consent_pending"] is True

    returning = VoiceSession("voice-isolation", "call-a2", caller_phone="911111111111")
    await returning.initialize()
    assert returning.consent_accepted
    assert returning.contact_id == first.contact_id
    assert returning.contact_id != second.contact_id

    ephemeral_a = VoiceSession("voice-isolation", "anonymous-a")
    ephemeral_b = VoiceSession("voice-isolation", "anonymous-b")
    await ephemeral_a.initialize()
    await ephemeral_b.initialize()
    assert ephemeral_a.contact_id != ephemeral_b.contact_id


async def test_verified_call_duration_is_metered_once_and_callback_mismatch_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = get_db()
    tenant_id = "voice-metering"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "voice_number": "919999999997",
            "timezone": "Asia/Kolkata",
        }
    )
    verified = {
        "Sid": "metered-call",
        "To": "919999999997",
        "From": "919876543210",
        "Status": "completed",
        "EndTime": "2026-08-01 00:01:00",
        "Details": {"ConversationDuration": 61},
    }
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.gateway.exotel.verify_exotel_call", AsyncMock(return_value=verified)
    )
    client = TestClient(app)
    payload = {
        "CallSid": "metered-call",
        "To": "919999999997",
        "From": "919876543210",
        "ConversationDuration": "61",
    }

    first = client.post("/webhooks/exotel/status", data=payload)
    replay = client.post("/webhooks/exotel/status", data=payload)
    mismatch = client.post(
        "/webhooks/exotel/status", data={**payload, "ConversationDuration": "99"}
    )

    assert first.json() == {"status": "recorded", "duration_seconds": 61}
    assert replay.json() == {"status": "duplicate", "duration_seconds": 61}
    assert mismatch.status_code == 409
    assert await db["usage_events"].count_documents(
        {"tenant_id": tenant_id, "metric": "voice_audio_seconds"}
    ) == 1
    meter = await db["usage_meters"].find_one(
        {"tenant_id": tenant_id, "period": "2026-08"}
    )
    assert meter["voice_audio_seconds"] == 61
