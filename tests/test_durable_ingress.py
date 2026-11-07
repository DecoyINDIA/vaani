from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from app.main import app
from app.models.base import get_db
from app.models.collections import Messages, OutboundIntents
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})
    await db["tenants"].insert_one({"_id": "t_ingress", "wa_number": "919999999999"})


def payload() -> dict:
    messages = [
        {"id": "wamid.1", "from": "911", "type": "text", "text": {"body": "one"}},
        {"id": "wamid.2", "from": "922", "type": "text", "text": {"body": "two"}},
    ]
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "919999999999"},
                            "messages": messages,
                        }
                    }
                ]
            }
        ]
    }


def test_complete_batch_is_durable_when_redis_is_down() -> None:
    unavailable = AsyncMock(side_effect=ConnectionError("redis down"))
    with patch("app.gateway.meta.get_redis") as redis:
        redis.return_value.xadd = unavailable
        response = TestClient(app).post("/webhooks/meta", json=payload())

    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "accepted": 2}

    async def verify() -> None:
        docs = await get_db()["messages"].find({"status": "queued"}).to_list(length=10)
        assert {doc["_id"] for doc in docs} == {"wamid.1", "wamid.2"}
        assert {doc["payload"]["entry"][0]["changes"][0]["value"]["messages"][0]["id"] for doc in docs} == {"wamid.1", "wamid.2"}

    asyncio.run(verify())


async def test_only_one_worker_acquires_an_event() -> None:
    await Messages.accept_inbound_unscoped("wamid.race", "t_ingress", payload())
    results = await asyncio.gather(
        Messages.acquire_work_unscoped("wamid.race"),
        Messages.acquire_work_unscoped("wamid.race"),
    )
    assert sum(result is not None for result in results) == 1


def test_mongo_failure_is_not_acknowledged() -> None:
    with patch.object(
        Messages, "accept_inbound_unscoped", AsyncMock(side_effect=ConnectionError("mongo down"))
    ):
        response = TestClient(app).post("/webhooks/meta", json=payload())
    assert response.status_code == 503


def test_provider_delivery_status_reconciles_outbound_intent() -> None:
    async def seed() -> None:
        await OutboundIntents("t_ingress").insert_one(
            {
                "operation_key": "status-test",
                "state": "sent",
                "provider_message_id": "wamid.outbound",
            }
        )

    asyncio.run(seed())
    status_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "919999999999"},
                            "statuses": [{"id": "wamid.outbound", "status": "delivered"}],
                        }
                    }
                ]
            }
        ]
    }
    response = TestClient(app).post("/webhooks/meta", json=status_payload)
    assert response.status_code == 200

    async def verify() -> None:
        intent = await OutboundIntents("t_ingress").find_one(
            {"operation_key": "status-test"}
        )
        assert intent is not None
        assert intent["state"] == "delivered"

    asyncio.run(verify())
