"""Inbound worker — Redis Streams consumer (TRD §1, Week 3 task 3.3).

Consumer group; dead-letter after 3 retries. Kill mid-message -> reprocessed, not
lost. Pulls normalized inbound events, runs the agent graph, sends the reply
through app.channels + app.audit. Entrypoint: `python -m app.workers.inbound`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app import audit
from app.agent.graph import build_graph
from app.channels.whatsapp import WindowClosedError, send_freeform
from app.gateway.middleware import get_redis
from app.models.collections import Contacts, Conversations, Messages

logger = logging.getLogger(__name__)

STREAM = "vaani:inbound_stream"
DEAD_LETTER = "vaani:inbound_dlq"
GROUP = "vaani:workers"
CONSUMER = "worker-1"
MAX_DELIVERIES = 3  # dead-letter after 3 failed attempts (kill-safe reprocessing)
_IDLE_RECLAIM_MS = 60_000  # reclaim messages stalled longer than 60s


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pull sender wa_id + text out of a Meta Cloud API webhook payload."""
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        msg = value["messages"][0]
    except (KeyError, IndexError):
        return None

    wa_id = msg.get("from") or (value.get("contacts") or [{}])[0].get("wa_id")
    if not wa_id:
        return None

    text = ""
    if msg.get("type") == "text":
        text = msg.get("text", {}).get("body", "")

    profile_name = ""
    contacts = value.get("contacts") or []
    if contacts:
        profile_name = contacts[0].get("profile", {}).get("name", "")

    return {"wa_id": wa_id, "text": text, "profile_name": profile_name}


async def _resolve_conversation(tenant_id: str, wa_id: str, name: str) -> str:
    """Upsert the contact (refresh 24h-window ts) and open/find its conversation."""
    contacts = Contacts(tenant_id)
    await contacts.update_one(
        {"wa_id": wa_id},
        {
            "$set": {"wa_id": wa_id, "last_inbound_ts": _now()},
            "$setOnInsert": {"name": name or wa_id, "created_at": _now()},
        },
        upsert=True,
    )
    contact = await contacts.find_one({"wa_id": wa_id})
    contact_id = str(contact["_id"]) if contact else wa_id

    conversations = Conversations(tenant_id)
    convo = await conversations.find_one({"contact_id": contact_id, "state": "open"})
    if convo:
        return str(convo["_id"])

    result = await conversations.insert_one(
        {"contact_id": contact_id, "channel": "wa", "state": "open", "started_at": _now()}
    )
    return str(result.inserted_id)


async def process_event(fields: dict[str, Any]) -> None:
    """Run one inbound event end-to-end: agent graph -> WhatsApp reply."""
    tenant_id = fields["tenant_id"]
    payload = json.loads(fields["payload"])

    parsed = _parse_message(payload)
    if not parsed or not parsed["text"]:
        logger.info("Skipping non-text / unparseable inbound event")
        return

    wa_id, text = parsed["wa_id"], parsed["text"]
    conversation_id = await _resolve_conversation(tenant_id, wa_id, parsed["profile_name"])

    await audit.record(
        tenant_id,
        actor="user",
        event_type="inbound_message",
        payload={"wa_id": wa_id, "text": text},
        conversation_id=conversation_id,
    )

    app = build_graph()
    state = {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "channel": "wa",
        "text": text,
    }
    result = await app.ainvoke(state)
    response = result.get("response", "")

    messages = Messages(tenant_id)
    await messages.insert_one(
        {
            "conversation_id": conversation_id,
            "direction": "inbound",
            "type": "text",
            "text": text,
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "ts": _now(),
        }
    )

    if not response:
        logger.warning("Agent produced an empty response for %s; nothing to send", wa_id)
        return

    try:
        await send_freeform(tenant_id, wa_id, response)
    except WindowClosedError:
        # Directly after an inbound message the window is open, so this is an edge
        # case (clock skew / very slow processing). Escalate rather than drop.
        logger.warning("24h window closed while replying to %s; leaving for staff", wa_id)
        await audit.record(
            tenant_id,
            actor="system",
            event_type="reply_window_closed",
            payload={"wa_id": wa_id, "response": response},
            conversation_id=conversation_id,
        )
        return

    await messages.insert_one(
        {
            "conversation_id": conversation_id,
            "direction": "outbound",
            "type": "text",
            "text": response,
            "ts": _now(),
        }
    )


async def _ensure_group(r: Any) -> None:
    try:
        await r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as e:  # redis.ResponseError: BUSYGROUP already exists
        if "BUSYGROUP" not in str(e):
            raise


async def _dead_letter(r: Any, msg_id: str, fields: dict[str, Any], reason: str) -> None:
    logger.error("Dead-lettering %s after %d attempts: %s", msg_id, MAX_DELIVERIES, reason)
    await r.xadd(DEAD_LETTER, {**fields, "failed_msg_id": msg_id, "reason": reason})
    await r.xack(STREAM, GROUP, msg_id)


async def _handle(r: Any, msg_id: str, fields: dict[str, Any], deliveries: int) -> None:
    try:
        await process_event(fields)
        await r.xack(STREAM, GROUP, msg_id)
    except Exception as e:
        if deliveries >= MAX_DELIVERIES:
            await _dead_letter(r, msg_id, fields, str(e))
        else:
            # Leave un-ACKed: it stays pending and is reclaimed for another attempt.
            logger.warning("Processing %s failed (attempt %d): %s", msg_id, deliveries, e)


async def run(iterations: int | None = None) -> None:
    """Consume the inbound stream. `iterations=None` runs forever (worker mode)."""
    r: Any = get_redis()  # redis-py stream ops are dynamically typed
    await _ensure_group(r)
    logger.info("Inbound worker consuming %s as %s/%s", STREAM, GROUP, CONSUMER)

    count = 0
    while iterations is None or count < iterations:
        count += 1

        # Reclaim stalled/failed pending messages, dead-lettering the exhausted ones.
        try:
            _, claimed, _ = await r.xautoclaim(
                STREAM, GROUP, CONSUMER, min_idle_time=_IDLE_RECLAIM_MS, start_id="0"
            )
            for msg_id, fields in claimed:
                pending = await r.xpending_range(STREAM, GROUP, msg_id, msg_id, 1)
                deliveries = int(pending[0]["times_delivered"]) if pending else MAX_DELIVERIES
                await _handle(r, msg_id, fields, deliveries)
        except Exception as e:
            logger.debug("xautoclaim skipped: %s", e)

        try:
            resp = await r.xreadgroup(
                GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000
            )
        except Exception as e:
            # Transient network/timeout on the blocking read must not kill the
            # consumer loop — log and retry rather than crash-looping the process.
            logger.warning("xreadgroup failed, retrying: %s", e)
            continue

        if not resp:
            continue
        for _stream, entries in resp:
            for msg_id, fields in entries:
                await _handle(r, msg_id, fields, deliveries=1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting inbound worker...")
    asyncio.run(run())


if __name__ == "__main__":
    main()
