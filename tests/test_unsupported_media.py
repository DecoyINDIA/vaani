from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from app.models.base import get_db
from app.models.collections import Conversations, Messages
from app.workers.inbound import UNSUPPORTED_REPLY, process_event


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


def _wa_media_payload(wa_id: str, msg_type: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "from": wa_id,
        "id": f"wamid.{wa_id}.{msg_type}",
        "type": msg_type,
    }
    if extra:
        msg[msg_type] = extra
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Media Patient"}}],
                            "messages": [msg],
                        }
                    }
                ]
            }
        ]
    }


@pytest.mark.asyncio
async def test_audio_message_replies_once_with_unsupported_text() -> None:
    tenant_id = "t_media"
    wa_id = "919876543201"
    payload = _wa_media_payload(wa_id, "audio", {"id": "audio-123", "mime_type": "audio/ogg"})
    event = {
        "tenant_id": tenant_id,
        "message_id": "msg-audio-1",
        "payload": json.dumps(payload),
    }

    # Process first time
    await process_event(event)

    # Inbound stored with type == "audio"
    inbound_msg = await Messages(tenant_id).find_one({"direction": "inbound"})
    assert inbound_msg is not None
    assert inbound_msg["type"] == "audio"
    assert inbound_msg["text"] == ""

    # Exactly one outbound text message equal to UNSUPPORTED_REPLY
    outbounds = await Messages(tenant_id).find({"direction": "outbound"}).to_list(10)
    assert len(outbounds) == 1
    assert outbounds[0]["text"] == UNSUPPORTED_REPLY

    # Conversation has last_msg_at
    conv = await Conversations(tenant_id).find_one({"tenant_id": tenant_id})
    assert conv is not None
    assert isinstance(conv.get("last_msg_at"), datetime)


@pytest.mark.asyncio
async def test_duplicate_audio_event_deduplicates_outbound() -> None:
    tenant_id = "t_media_dup"
    wa_id = "919876543202"
    payload = _wa_media_payload(wa_id, "audio", {"id": "audio-456"})
    event = {
        "tenant_id": tenant_id,
        "message_id": "msg-audio-dup",
        "payload": json.dumps(payload),
    }

    await process_event(event)
    await process_event(event)

    outbounds = await Messages(tenant_id).find({"direction": "outbound"}).to_list(10)
    assert len(outbounds) == 1


@pytest.mark.asyncio
async def test_human_state_stores_media_without_outbound() -> None:
    tenant_id = "t_media_human"
    wa_id = "919876543203"
    db = get_db()
    # Pre-create contact and conversation in human state
    contact_res = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "phone": wa_id,
            "name": "Human Patient",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    await db["conversations"].insert_one(
        {
            "tenant_id": tenant_id,
            "contact_id": str(contact_res.inserted_id),
            "channel": "wa",
            "state": "human",
            "started_at": datetime.now(UTC).replace(tzinfo=None),
        }
    )

    payload = _wa_media_payload(wa_id, "image", {"id": "img-789"})
    event = {
        "tenant_id": tenant_id,
        "message_id": "msg-img-1",
        "payload": json.dumps(payload),
    }
    await process_event(event)

    inbound_msg = await Messages(tenant_id).find_one({"direction": "inbound"})
    assert inbound_msg is not None
    assert inbound_msg["type"] == "image"

    outbound_count = await Messages(tenant_id).count_documents({"direction": "outbound"})
    assert outbound_count == 0


@pytest.mark.asyncio
async def test_reaction_is_ignored_and_not_stored() -> None:
    tenant_id = "t_media_reaction"
    wa_id = "919876543204"
    payload = _wa_media_payload(wa_id, "reaction", {"message_id": "wamid.123", "emoji": "👍"})
    event = {
        "tenant_id": tenant_id,
        "message_id": "msg-react-1",
        "payload": json.dumps(payload),
    }
    await process_event(event)

    assert await Messages(tenant_id).count_documents({}) == 0
    assert await Conversations(tenant_id).count_documents({}) == 0


@pytest.mark.asyncio
async def test_text_inbound_sets_last_msg_at() -> None:
    tenant_id = "t_media_text"
    wa_id = "919876543205"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Text Patient"}}],
                            "messages": [{"from": wa_id, "id": "wamid.txt", "type": "text", "text": {"body": "hello"}}],
                        }
                    }
                ]
            }
        ]
    }
    event = {
        "tenant_id": tenant_id,
        "message_id": "msg-txt-1",
        "payload": json.dumps(payload),
    }
    await process_event(event)

    conv = await Conversations(tenant_id).find_one({"tenant_id": tenant_id})
    assert conv is not None
    assert isinstance(conv.get("last_msg_at"), datetime)
