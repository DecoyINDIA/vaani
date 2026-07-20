"""Meta WhatsApp Cloud API webhook (TRD §5.1, ADR-04).

GET  /webhooks/meta  — verification handshake (hub.challenge).
POST /webhooks/meta  — signature-verified, idempotent on message_id, must ack
                        <5s then process async via Redis Streams (Week 3, 3.2/3.3).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Request, Response

from app import audit
from app.config import settings
from app.gateway.middleware import claim_message, get_redis, resolve_tenant, verify_meta_signature
from app.models.collections import Messages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.get("/meta")
async def verify(request: Request) -> Response:
    """Meta verification handshake — echo hub.challenge when the token matches."""
    params = request.query_params
    mode = params.get("hub.mode")
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and verify_token == settings.meta_webhook_verify_token:
        logger.info("Webhook verified successfully")
        return Response(content=challenge, media_type="text/plain")
    
    logger.warning("Webhook verification failed: token mismatch")
    return Response(content="Verification token mismatch", status_code=403, media_type="text/plain")


@router.post("/meta")
async def receive(request: Request) -> Response:
    """Ack fast (200), then enqueue for the inbound worker. No processing inline."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    # 1. Verify Meta Signature
    if not verify_meta_signature(body, signature):
        logger.warning("Invalid webhook signature")
        return Response(content="Invalid signature", status_code=403)

    # 2. Parse Body and handle empty/ping payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Malformed webhook JSON payload")
        # Ack malformed payloads to avoid Meta retries
        return Response(content="Malformed JSON", status_code=200)

    # Extract messages and metadata
    entry = payload.get("entry", [])
    if not entry or not entry[0].get("changes", []):
        return Response(content='{"status":"no_changes"}', status_code=200)

    change = entry[0]["changes"][0]
    value = change.get("value", {})
    messages = value.get("messages", [])

    if not messages:
        # Ping or read/delivered status updates — ack and ignore for the MVP worker
        return Response(content='{"status":"ignored"}', status_code=200)

    msg = messages[0]
    message_id = msg.get("id")
    metadata = value.get("metadata", {})
    wa_number = metadata.get("display_phone_number")

    if not message_id or not wa_number:
        logger.warning("Webhook missing message_id or wa_number")
        return Response(content='{"status":"invalid_payload"}', status_code=200)

    # 3. Check Message Idempotency
    is_new = await claim_message(message_id)
    if not is_new:
        logger.info(f"Duplicate message delivery ignored: {message_id}")
        return Response(content='{"status":"duplicate"}', status_code=200)

    # 4. Resolve Tenant
    try:
        tenant_id = await resolve_tenant(wa_number)
    except ValueError as e:
        logger.warning(f"Tenant resolution failed: {e}")
        # Audit entry for unknown wa_number (platform-level, tenant "SYSTEM")
        try:
            await audit.record(
                "SYSTEM",
                actor="system",
                event_type="unknown_recipient",
                payload={"wa_number": wa_number, "message_id": message_id},
            )
        except Exception as audit_err:
            logger.error(f"Failed to write audit log for unknown recipient: {audit_err}")
        return Response(content='{"status":"unknown_recipient"}', status_code=200)

    # 5. Enqueue Message
    stream_payload: dict[str, str] = {
        "tenant_id": tenant_id,
        "message_id": message_id,
        "payload": json.dumps(payload)
    }

    try:
        r = get_redis()
        # Enqueue to Redis stream. redis-py's xadd stub declares an invariant dict
        # type that a plain dict[str, str] never satisfies; cast to Any to bypass.
        await r.xadd("vaani:inbound_stream", cast(Any, stream_payload))
        logger.info(f"Enqueued message {message_id} to Redis Stream")
    except Exception as e:
        logger.warning(f"Redis enqueuing failed, falling back to MongoDB: {e}")
        try:
            # MongoDB Fallback Queue
            await Messages.upsert_fallback_message_unscoped(
                tenant_id=tenant_id,
                message_id=message_id,
                document={
                    "conversation_id": "fallback_queue",
                    "direction": "inbound",
                    "type": "text",
                    "text": msg.get("text", {}).get("body", ""),
                    "status": "queued",
                    "payload": payload,
                    "ts": datetime.now(UTC).replace(tzinfo=None),
                    "retries": 0,
                }
            )
            logger.info(f"Enqueued message {message_id} to MongoDB fallback queue")
        except Exception as db_err:
            logger.critical(f"MongoDB fallback queue also failed! Message lost: {db_err}")
            return Response(content='{"status":"critical_failure"}', status_code=200)

    return Response(content='{"status":"accepted"}', status_code=200)

