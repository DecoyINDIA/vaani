from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.channels.voice.session import VoiceSession
from app.config import settings
from app.gateway.exotel import (
    consume_stream_grant,
    issue_stream_grant,
    start_outbound_call,
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


def test_unverified_missed_call_callback_is_rejected() -> None:
    response = TestClient(app).post(
        "/webhooks/exotel/missed_call",
        data={
            "To": "919999999998",
            "From": "919876543299",
            "CallSid": "attacker-selected-missed-call",
        },
    )
    assert response.status_code == 401


async def test_verified_missed_call_callback_triggers_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    db = get_db()
    tenant_id = "test_tenant"
    await db["tenants"].update_one(
        {"_id": tenant_id},
        {"$set": {"voice_number": "919999999998", "name": "Sharma Dental Clinic"}},
        upsert=True,
    )
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.gateway.exotel.verify_exotel_call",
        AsyncMock(return_value={"Sid": "verified-missed-call"}),
    )
    monkeypatch.setattr(
        "app.channels.whatsapp.send_template",
        AsyncMock(return_value={"status": "sent"}),
    )
    client = TestClient(app)
    response = client.post(
        "/webhooks/exotel/missed_call",
        data={
            "To": "919999999998",
            "From": "919876543299",
            "CallSid": "verified-missed-call",
        },
    )
    assert response.status_code == 200
    contact = await db["contacts"].find_one({"tenant_id": tenant_id, "phone": "919876543299"})
    assert contact is not None
    conv = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "contact_id": str(contact["_id"])}
    )
    assert conv is not None
    assert conv["state"] == "bot"


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


async def test_outbound_call_uses_authenticated_bidirectional_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = "outbound-voice-tenant"
    await get_db()["tenants"].update_one(
        {"_id": tenant_id},
        {"$set": {"voice_number": "08040000000"}},
        upsert=True,
    )
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"Call": {"Sid": "outbound-call-sid", "Status": "queued"}}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Response:
            captured.update({"url": url, **kwargs})
            return Response()

    monkeypatch.setattr(settings, "exotel_sid", "account-sid")
    monkeypatch.setattr(settings, "exotel_api_key", "api-key")
    monkeypatch.setattr(settings, "exotel_api_token", "api-token")
    monkeypatch.setattr(settings, "exotel_subdomain", "api.in.exotel.com")
    monkeypatch.setattr(settings, "voice_public_base_url", "https://voice.example.com")
    monkeypatch.setattr("app.gateway.exotel.httpx.AsyncClient", Client)

    result = await start_outbound_call(tenant_id, "+919876543210")

    assert result == {"call_sid": "outbound-call-sid", "status": "queued"}
    assert captured["url"] == (
        "https://api.in.exotel.com/v1/Accounts/account-sid/Calls/connect"
    )
    assert captured["auth"] == ("api-key", "api-token")
    assert captured["data"]["StreamType"] == "bidirectional"
    assert captured["data"]["Record"] == "false"
    assert captured["data"]["StreamUrl"].startswith(
        "wss://voice.example.com/webhooks/stream/outbound-voice-tenant/out_"
    )
    assert captured["data"]["StatusCallback"] == (
        "https://voice.example.com/webhooks/exotel/status"
    )
    grant = await get_db()["voice_grants"].find_one({"tenant_id": tenant_id})
    assert grant is not None
    assert grant["caller_phone"] == "+919876543210"


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


async def test_websocket_stream_grant_security_boundaries() -> None:
    from fastapi import WebSocketDisconnect

    client = TestClient(app)
    db = get_db()
    await db["tenants"].update_one(
        {"_id": "test_tenant"},
        {"$set": {"voice_number": "919999999998"}},
        upsert=True,
    )
    # 1. No token provided -> 4003
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/webhooks/stream/test_tenant/call-ws-no-token") as ws:
            ws.receive_json()
    assert exc.value.code == 4003

    # 2. Token issued for call-1, caller-1
    token = await issue_stream_grant("test_tenant", "call-ws-1", "919876543210")
    assert token is not None

    # Mismatched caller query param -> 4003
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/webhooks/stream/test_tenant/call-ws-1?token={token}&caller_phone=919999999999"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4003

    # Wrong tenant in path -> 4003
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/webhooks/stream/other_tenant/call-ws-1?token={token}&caller_phone=919876543210"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4003

    # Wrong call_sid in path -> 4003
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/webhooks/stream/test_tenant/wrong-call?token={token}&caller_phone=919876543210"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4003

    # Tampered signature -> 4003
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.{'0' * len(parts[2])}"
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/webhooks/stream/test_tenant/call-ws-1?token={tampered}&caller_phone=919876543210"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4003

    # Successful connection consumes token once
    with client.websocket_connect(
        f"/webhooks/stream/test_tenant/call-ws-1?token={token}&caller_phone=919876543210"
    ) as ws:
        ws.send_json({"event": "connected"})

    # Replay of consumed token is rejected -> 4003
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/webhooks/stream/test_tenant/call-ws-1?token={token}&caller_phone=919876543210"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4003


async def test_voice_stream_session_cleanup_on_disconnect() -> None:
    client = TestClient(app)
    db = get_db()
    tenant_id = "test_tenant"
    await db["tenants"].update_one(
        {"_id": tenant_id},
        {"$set": {"voice_number": "919999999998"}},
        upsert=True,
    )
    token = await issue_stream_grant(tenant_id, "call-cleanup-test", "919876543210")
    assert token is not None

    with client.websocket_connect(
        f"/webhooks/stream/{tenant_id}/call-cleanup-test?token={token}&caller_phone=919876543210"
    ):
        pass

    conv = await db["conversations"].find_one(
        {"tenant_id": tenant_id, "_id": "conv_call-cleanup-test"}
    )
    assert conv is not None
    assert conv["state"] == "closed"
    assert conv["ended_at"] is not None
