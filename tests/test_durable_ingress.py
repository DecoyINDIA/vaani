from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.main import app
from app.models.base import get_db
from app.models.collections import Messages, OutboundIntents
from app.workers import inbound
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


async def test_transcript_keeps_recovery_payload_until_completion() -> None:
    message_id = "wamid.crash-window"
    await Messages.accept_inbound_unscoped(message_id, "t_ingress", payload())
    assert await Messages.acquire_work_unscoped(message_id) is not None

    await Messages.upsert_message_unscoped(
        message_id,
        "t_ingress",
        {"direction": "inbound", "type": "text", "text": "committed"},
    )
    in_flight = await get_db()["messages"].find_one({"_id": message_id})
    assert in_flight is not None
    assert in_flight["status"] == "processing"
    assert in_flight["payload"] == payload()

    await Messages.mark_completed_unscoped(message_id)
    completed = await get_db()["messages"].find_one({"_id": message_id})
    assert completed is not None
    assert "status" not in completed
    assert "payload" not in completed
    assert "lease_expires_at" not in completed
    assert isinstance(completed["processed_at"], datetime)


async def test_stream_ack_happens_after_durable_completion() -> None:
    message_id = "wamid.stream-complete"
    event = payload()
    await Messages.accept_inbound_unscoped(message_id, "t_ingress", event)
    fields = {
        "tenant_id": "t_ingress",
        "message_id": message_id,
        "payload": json.dumps(event),
    }

    async def record_transcript(_: dict[str, str]) -> None:
        await Messages.upsert_message_unscoped(
            message_id,
            "t_ingress",
            {"direction": "inbound", "type": "text", "text": "processed"},
        )

    redis = AsyncMock()
    with patch.object(inbound, "process_event", side_effect=record_transcript):
        await inbound._handle(redis, "stream-id", fields, deliveries=1)

    redis.xack.assert_awaited_once_with(inbound.STREAM, inbound.GROUP, "stream-id")
    completed = await get_db()["messages"].find_one({"_id": message_id})
    assert completed is not None
    assert completed["text"] == "processed"
    assert "status" not in completed
    assert "payload" not in completed


async def test_expired_crash_lease_recovers_without_redis() -> None:
    message_id = "wamid.abandoned"
    event = payload()
    await Messages.accept_inbound_unscoped(message_id, "t_ingress", event)
    assert await Messages.acquire_work_unscoped(message_id) is not None
    await get_db()["messages"].update_one(
        {"_id": message_id},
        {"$set": {"lease_expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)}},
    )

    with patch.object(inbound, "process_event", AsyncMock()) as process:
        await inbound._process_fallback_queue()

    process.assert_awaited_once()
    fields = process.await_args.args[0]
    assert fields["message_id"] == message_id
    assert fields["tenant_id"] == "t_ingress"
    completed = await get_db()["messages"].find_one({"_id": message_id})
    assert completed is not None
    assert "status" not in completed
    assert "payload" not in completed
    assert completed["attempts"] == 2


async def test_replayed_inbound_event_records_one_audit() -> None:
    await get_db()["contacts"].insert_one(
        {"_id": "audit-contact", "tenant_id": "t_ingress", "wa_id": "933"}
    )
    await get_db()["conversations"].insert_one(
        {
            "_id": "audit-conversation",
            "tenant_id": "t_ingress",
            "contact_id": "audit-contact",
            "channel": "wa",
            "state": "human",
        }
    )
    event = {
        "entry": [{"changes": [{"value": {
            "metadata": {"display_phone_number": "919999999999"},
            "messages": [{
                "id": "wamid.audit", "from": "933", "type": "text",
                "text": {"body": "replayed message"},
            }],
        }}]}]
    }
    fields = {
        "tenant_id": "t_ingress",
        "message_id": "wamid.audit",
        "payload": json.dumps(event),
    }

    await inbound.process_event(fields)
    await inbound.process_event(fields)

    audits = await get_db()["audit_log"].count_documents(
        {"tenant_id": "t_ingress", "operation_key": "inbound:wamid.audit"}
    )
    assert audits == 1


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
