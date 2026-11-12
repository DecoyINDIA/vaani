from __future__ import annotations

import asyncio
import json
import socket
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.config import settings
from app.models.base import get_db
from app.models.collections import Messages
from app.workers import inbound


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})
    await db["tenants"].insert_one({"_id": "t_conc", "wa_number": "919999999999"})


def _wa_payload(sender: str, text: str, msg_id: str | None = None) -> dict:
    mid = msg_id or f"wamid.{sender}"
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "919999999999"},
                            "contacts": [{"wa_id": sender, "profile": {"name": f"P-{sender}"}}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": mid,
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


async def test_eight_patients_run_concurrently() -> None:
    tenant_id = "t_conc"
    senders = [f"91900000000{i}" for i in range(8)]
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)

    for i, s in enumerate(senders):
        mid = f"wamid.conc.{i}"
        await Messages.accept_inbound_unscoped(mid, tenant_id, _wa_payload(s, f"hello {i}", mid))
        await get_db()["messages"].update_one(
            {"_id": mid},
            {"$set": {"accepted_at": base_time + timedelta(seconds=i)}},
        )

    current_concurrent = 0
    max_concurrent = 0
    lock = asyncio.Lock()
    processed: list[str] = []

    async def fake_process(fields: dict) -> None:
        nonlocal current_concurrent, max_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        await asyncio.sleep(0.05)
        async with lock:
            current_concurrent -= 1
            processed.append(fields["message_id"])

    with patch.object(settings, "worker_concurrency", 8):
        with patch.object(inbound, "process_event", side_effect=fake_process):
            await inbound._process_fallback_queue()

    assert len(processed) == 8
    assert max_concurrent >= 4

    # All 8 are marked completed
    completed_count = await get_db()["messages"].count_documents(
        {"tenant_id": tenant_id, "processed_at": {"$type": "date"}}
    )
    assert completed_count == 8


async def test_five_events_same_patient_run_in_order_strictly_sequential() -> None:
    tenant_id = "t_conc"
    sender = "919876543210"
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)

    msg_ids = [f"wamid.order.{i}" for i in range(5)]
    for i, mid in enumerate(msg_ids):
        await Messages.accept_inbound_unscoped(mid, tenant_id, _wa_payload(sender, f"msg {i}", mid))
        await get_db()["messages"].update_one(
            {"_id": mid},
            {"$set": {"accepted_at": base_time + timedelta(seconds=i * 2)}},
        )

    current_concurrent = 0
    max_concurrent = 0
    lock = asyncio.Lock()
    processed_order: list[str] = []

    async def fake_process(fields: dict) -> None:
        nonlocal current_concurrent, max_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        # Small delay to verify serial execution
        await asyncio.sleep(0.02)
        async with lock:
            current_concurrent -= 1
            processed_order.append(fields["message_id"])

    with patch.object(settings, "worker_concurrency", 8):
        with patch.object(inbound, "process_event", side_effect=fake_process):
            await inbound._process_fallback_queue()

    assert processed_order == msg_ids
    assert max_concurrent == 1


async def test_failing_event_does_not_stop_later_or_other_events() -> None:
    tenant_id = "t_conc"
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)

    # Patient A: m_a1 (fails), m_a2 (succeeds)
    # Patient B: m_b1 (succeeds)
    await Messages.accept_inbound_unscoped(
        "m_a1", tenant_id, _wa_payload("919111111111", "fail me", "m_a1")
    )
    await Messages.accept_inbound_unscoped(
        "m_a2", tenant_id, _wa_payload("919111111111", "succeed me", "m_a2")
    )
    await Messages.accept_inbound_unscoped(
        "m_b1", tenant_id, _wa_payload("919222222222", "succeed b", "m_b1")
    )

    await get_db()["messages"].update_one(
        {"_id": "m_a1"}, {"$set": {"accepted_at": base_time}}
    )
    await get_db()["messages"].update_one(
        {"_id": "m_a2"}, {"$set": {"accepted_at": base_time + timedelta(seconds=1)}}
    )
    await get_db()["messages"].update_one(
        {"_id": "m_b1"}, {"$set": {"accepted_at": base_time + timedelta(seconds=2)}}
    )

    processed: list[str] = []

    async def fake_process(fields: dict) -> None:
        mid = fields["message_id"]
        if mid == "m_a1":
            raise RuntimeError("synthetic processing error on a1")
        processed.append(mid)

    with patch.object(settings, "worker_concurrency", 8):
        with patch.object(inbound, "process_event", side_effect=fake_process):
            await inbound._process_fallback_queue()

    # m_a2 and m_b1 both succeeded despite m_a1 failure
    assert "m_a2" in processed
    assert "m_b1" in processed

    # m_a1 was released back to queued with last_error recorded
    m_a1_doc = await get_db()["messages"].find_one({"_id": "m_a1"})
    assert m_a1_doc is not None
    assert m_a1_doc["status"] == "queued"


async def test_duplicate_delivery_processed_once() -> None:
    tenant_id = "t_conc"
    mid = "wamid.dup"
    await Messages.accept_inbound_unscoped(
        mid, tenant_id, _wa_payload("919333333333", "dup test", mid)
    )

    call_count = 0

    async def fake_process(_: dict) -> None:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)

    redis = AsyncMock()
    fields = {
        "tenant_id": tenant_id,
        "message_id": mid,
        "payload": json.dumps(_wa_payload("919333333333", "dup test", mid)),
    }

    with patch.object(inbound, "process_event", side_effect=fake_process):
        # Run two concurrent _handle attempts on the same message
        await asyncio.gather(
            inbound._handle(redis, mid, fields, deliveries=1),
            inbound._handle(redis, mid, fields, deliveries=1),
        )

    assert call_count == 1


def test_consumer_differs_between_simulated_pids() -> None:
    c1 = inbound.make_consumer_name(pid=1001)
    c2 = inbound.make_consumer_name(pid=1002)
    assert c1 != c2
    assert c1.endswith("-1001")
    assert c2.endswith("-1002")

    with patch("os.getpid", return_value=4242):
        assert inbound.make_consumer_name() == f"{socket.gethostname()}-4242"

    assert inbound.CONSUMER.startswith(socket.gethostname())


def test_get_graph_returns_same_object() -> None:
    g1 = inbound.get_graph()
    g2 = inbound.get_graph()
    assert g1 is g2


async def test_worker_concurrency_rollback_switch() -> None:
    tenant_id = "t_conc"
    senders = [f"91944444400{i}" for i in range(5)]
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)

    for i, s in enumerate(senders):
        mid = f"wamid.rollback.{i}"
        await Messages.accept_inbound_unscoped(mid, tenant_id, _wa_payload(s, f"rb {i}", mid))
        await get_db()["messages"].update_one(
            {"_id": mid},
            {"$set": {"accepted_at": base_time + timedelta(seconds=i)}},
        )

    current_concurrent = 0
    max_concurrent = 0
    lock = asyncio.Lock()
    processed: list[str] = []

    async def fake_process(fields: dict) -> None:
        nonlocal current_concurrent, max_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        await asyncio.sleep(0.02)
        async with lock:
            current_concurrent -= 1
            processed.append(fields["message_id"])

    # Concurrency forced to 1 (rollback setting)
    with patch.object(settings, "worker_concurrency", 1):
        with patch.object(inbound, "process_event", side_effect=fake_process):
            await inbound._process_fallback_queue()

    assert len(processed) == 5
    assert max_concurrent == 1


def test_contact_key_resolution() -> None:
    # 1. Normal payload with sender from
    p1 = _wa_payload("919555555555", "hi", "w1")
    assert inbound._contact_key("t1", p1) == "t1:919555555555"

    # 2. Payload with contacts wa_id but no messages from
    p2 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "919666666666"}],
                            "messages": [{"id": "w2", "text": {"body": "hi"}}],
                        }
                    }
                ]
            }
        ]
    }
    assert inbound._contact_key("t1", p2) == "t1:919666666666"

    # 3. Payload with message id only
    p3 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [{"id": "w3", "text": {"body": "hi"}}],
                        }
                    }
                ]
            }
        ]
    }
    assert inbound._contact_key("t1", p3) == "t1:w3"

    # 4. Unknown payload
    assert inbound._contact_key("t1", {}) == "t1:unknown"
    assert inbound._contact_key("t1", {}, message_id="custom_mid") == "t1:custom_mid"


async def test_twenty_conversation_concurrency_soak() -> None:
    """INT-2 Checkpoint: 20 concurrent conversations across 20 distinct patients with multiple messages."""
    tenant_id = "t_conc"
    patients = [f"9198000000{i:02d}" for i in range(20)]
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)

    # Seed 2 sequential messages per patient (40 total)
    for p_idx, p_num in enumerate(patients):
        m1 = f"wamid.soak.{p_idx}.1"
        m2 = f"wamid.soak.{p_idx}.2"
        await Messages.accept_inbound_unscoped(
            m1, tenant_id, _wa_payload(p_num, f"msg1 from {p_num}", m1)
        )
        await Messages.accept_inbound_unscoped(
            m2, tenant_id, _wa_payload(p_num, f"msg2 from {p_num}", m2)
        )
        await get_db()["messages"].update_one(
            {"_id": m1},
            {"$set": {"accepted_at": base_time + timedelta(seconds=p_idx * 2)}},
        )
        await get_db()["messages"].update_one(
            {"_id": m2},
            {"$set": {"accepted_at": base_time + timedelta(seconds=p_idx * 2 + 1)}},
        )

    lock = asyncio.Lock()
    current_concurrent = 0
    max_concurrent = 0
    patient_processed: dict[str, list[str]] = {p: [] for p in patients}

    async def fake_process(fields: dict) -> None:
        nonlocal current_concurrent, max_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        await asyncio.sleep(0.01)
        async with lock:
            current_concurrent -= 1
            payload = json.loads(fields["payload"])
            sender = payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
            patient_processed[sender].append(fields["message_id"])

    with patch.object(settings, "worker_concurrency", 8):
        with patch.object(inbound, "process_event", side_effect=fake_process):
            await inbound._process_fallback_queue()

    # All 20 patients had both messages processed in exact arrival order
    for p_idx, p_num in enumerate(patients):
        m1 = f"wamid.soak.{p_idx}.1"
        m2 = f"wamid.soak.{p_idx}.2"
        assert patient_processed[p_num] == [m1, m2]

    # High concurrency observed across distinct patients
    assert max_concurrent >= 6

    # Zero failed messages
    failed_count = await get_db()["messages"].count_documents({"status": "failed"})
    assert failed_count == 0

    # All 40 completed
    completed_count = await get_db()["messages"].count_documents(
        {"tenant_id": tenant_id, "processed_at": {"$type": "date"}}
    )
    assert completed_count == 40
