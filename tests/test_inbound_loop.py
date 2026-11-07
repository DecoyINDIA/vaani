"""End-to-end inbound loop (Week 3, tasks 3.3 + 3.7).

Proves the core message path is wired: a Meta webhook payload runs through the
agent graph and produces an audited WhatsApp reply, with the 24h send-window and
template registry enforced. Offline (no BSP creds) — sends are mocked.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from app.channels import whatsapp
from app.models.base import get_db
from app.models.collections import Contacts, Conversations
from app.workers import inbound


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


def _wa_payload(wa_id: str, text: str, name: str = "Patient") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": name}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{wa_id}",
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


async def test_inbound_event_produces_audited_reply():
    tenant_id = "t_loop"
    wa_id = "919812345678"
    fields = {
        "tenant_id": tenant_id,
        "message_id": f"wamid.{wa_id}",
        "payload": json.dumps(_wa_payload(wa_id, "what are your timings?")),
    }

    await inbound.process_event(fields)

    db = get_db()

    # Contact upserted with a fresh 24h-window timestamp.
    contact = await Contacts(tenant_id).find_one({"wa_id": wa_id})
    assert contact is not None
    assert isinstance(contact["last_inbound_ts"], datetime)
    assert await whatsapp._window_open(tenant_id, wa_id) is True

    # Both directions logged, tenant-scoped.
    msgs = await db["messages"].find({"tenant_id": tenant_id}).to_list(length=10)
    assert sorted(m["direction"] for m in msgs) == ["inbound", "outbound"]
    assert all(m["tenant_id"] == tenant_id for m in msgs)

    # The outbound send passed through the audit choke point.
    events = {
        a["event_type"]
        for a in await db["audit_log"].find({"tenant_id": tenant_id}).to_list(length=10)
    }
    assert "inbound_message" in events
    assert "outbound_freeform" in events


async def test_freeform_blocked_outside_window():
    tenant_id = "t_win"
    wa_id = "911111111111"
    await Contacts(tenant_id).insert_one(
        {
            "wa_id": wa_id,
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None)
            - timedelta(hours=25),
        }
    )
    with pytest.raises(whatsapp.WindowClosedError):
        await whatsapp.send_freeform(tenant_id, wa_id, "hi", operation_key="window-test")


async def test_template_send_and_registry_guard():
    tenant_id = "t_tpl"
    wa_id = "912222222222"

    result = await whatsapp.send_template(
        tenant_id,
        wa_id,
        "booking_confirm",
        {"name": "Asha", "time": "5pm"},
        operation_key="template-test",
    )
    assert result.get("mock") is True

    with pytest.raises(ValueError):
        await whatsapp.send_template(
            tenant_id, wa_id, "not_a_real_template", {}, operation_key="unknown-template"
        )


async def test_human_owned_conversation_records_without_bot_reply():
    tenant_id = "t_human"
    wa_id = "913333333333"
    await Contacts(tenant_id).insert_one({"_id": "contact-human", "wa_id": wa_id})
    await Conversations(tenant_id).insert_one(
        {"_id": "conversation-human", "contact_id": "contact-human", "state": "human"}
    )
    fields = {
        "tenant_id": tenant_id,
        "message_id": "wamid.human",
        "payload": json.dumps(_wa_payload(wa_id, "I still need help")),
    }

    await inbound.process_event(fields)

    messages = await get_db()["messages"].find({"tenant_id": tenant_id}).to_list(length=10)
    assert [(message["direction"], message["text"]) for message in messages] == [
        ("inbound", "I still need help")
    ]
