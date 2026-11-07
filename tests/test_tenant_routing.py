from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from app.channels.whatsapp import send_freeform, send_template
from app.config import settings
from app.models.base import get_db


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


async def test_two_tenants_route_to_their_own_sender_and_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = get_db()
    now = datetime.now(UTC).replace(tzinfo=None)
    for tenant_id, sender, token_env, wa_id in (
        ("routing-a", "sender-a", "VAANI_WA_TOKEN_A", "911111111111"),
        ("routing-b", "sender-b", "VAANI_WA_TOKEN_B", "922222222222"),
    ):
        await db["tenants"].insert_one(
            {
                "_id": tenant_id,
                "whatsapp": {"phone_number_id": sender, "access_token_env": token_env},
            }
        )
        await db["contacts"].insert_one(
            {"tenant_id": tenant_id, "wa_id": wa_id, "last_inbound_ts": now}
        )
    monkeypatch.setenv("VAANI_WA_TOKEN_A", "secret-token-a")
    monkeypatch.setenv("VAANI_WA_TOKEN_B", "secret-token-b")
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    calls: list[dict[str, Any]] = []

    class Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"messages": [{"id": f"wamid-{len(calls)}"}]}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Response:
            calls.append({"url": url, **kwargs})
            return Response()

    monkeypatch.setattr("app.channels.whatsapp.httpx.AsyncClient", Client)
    await send_freeform(
        "routing-a", "911111111111", "hello", operation_key="routing-a-reply"
    )
    await send_template(
        "routing-b",
        "922222222222",
        "reminder_24h",
        {
            "time": "09:00 AM",
            "patient_name": "B",
            "date": "Sunday, 08 November 2026",
            "doctor_name": "Dr B",
        },
        operation_key="routing-b-reminder",
        language_code="hi",
    )

    assert [call["url"] for call in calls] == [
        "https://graph.facebook.com/v20.0/sender-a/messages",
        "https://graph.facebook.com/v20.0/sender-b/messages",
    ]
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-token-a"
    assert calls[1]["headers"]["Authorization"] == "Bearer secret-token-b"
    assert calls[1]["json"]["template"]["language"] == {"code": "hi"}
    assert calls[1]["json"]["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": "B"},
        {"type": "text", "text": "Dr B"},
        {"type": "text", "text": "Sunday, 08 November 2026"},
        {"type": "text", "text": "09:00 AM"},
    ]


async def test_missing_tenant_channel_fails_before_delivery_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await get_db()["tenants"].insert_one({"_id": "routing-missing"})
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    with pytest.raises(RuntimeError, match="tenant WhatsApp configuration"):
        await send_template(
            "routing-missing",
            "933333333333",
            "reminder_24h",
            {
                "patient_name": "Patient",
                "doctor_name": "Doctor",
                "date": "Sunday, 08 November 2026",
                "time": "09:00 AM",
            },
            operation_key="must-not-persist",
        )
    assert await get_db()["outbound_intents"].count_documents(
        {"tenant_id": "routing-missing"}
    ) == 0
