"""Meta WhatsApp Cloud API webhook (TRD §5.1, ADR-04).

GET  /webhooks/meta  — verification handshake (hub.challenge).
POST /webhooks/meta  — signature-verified, idempotent on message_id, must ack
                        <5s then process async via Redis Streams (Week 3, 3.2/3.3).
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from fastapi import APIRouter, Request, Response
from pymongo.errors import DuplicateKeyError

from app import audit
from app.config import settings
from app.gateway.middleware import get_redis, resolve_tenant, verify_meta_signature
from app.models.collections import Messages, OutboundIntents
from app.privacy import is_suppressed

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

    accepted = duplicates = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            wa_number = value.get("metadata", {}).get("display_phone_number")
            if wa_number:
                try:
                    status_tenant_id = await resolve_tenant(str(wa_number))
                except ValueError:
                    status_tenant_id = None
                if status_tenant_id:
                    for status in value.get("statuses", []):
                        provider_id = status.get("id")
                        provider_state = status.get("status")
                        if provider_id and provider_state in {
                            "sent",
                            "delivered",
                            "read",
                            "failed",
                        }:
                            state = (
                                "delivered"
                                if provider_state in {"delivered", "read"}
                                else provider_state
                            )
                            await OutboundIntents(status_tenant_id).update_one(
                                {"provider_message_id": provider_id},
                                {
                                    "$set": {
                                        "state": state,
                                        "provider_status": provider_state,
                                    }
                                },
                            )
                            pricing = status.get("pricing", {})
                            if state == "delivered" and pricing.get("billable") is True:
                                from app.billing.meters import record_usage

                                await record_usage(
                                    status_tenant_id,
                                    event_id=f"meta:{provider_id}:billable",
                                    metric="meta_billable_messages",
                                    quantity=1,
                                )
            for msg in value.get("messages", []):
                message_id = msg.get("id")
                if not message_id or not wa_number:
                    logger.warning("Webhook message missing message_id or wa_number")
                    continue

                try:
                    tenant_id = await resolve_tenant(str(wa_number))
                except ValueError as e:
                    logger.warning("Tenant resolution failed: %s", e)
                    await audit.record(
                        "SYSTEM",
                        actor="system",
                        event_type="unknown_recipient",
                        payload={"wa_number": wa_number, "message_id": message_id},
                    )
                    continue

                sender = str(msg.get("from", ""))
                if sender and await is_suppressed(tenant_id, sender):
                    logger.info("Suppressed inbound event after erasure: %s", message_id)
                    continue

                event_payload = {
                    "entry": [{"changes": [{**change, "value": {**value, "messages": [msg]}}]}]
                }
                try:
                    await Messages.accept_inbound_unscoped(message_id, tenant_id, event_payload)
                except DuplicateKeyError:
                    duplicates += 1
                    continue
                except Exception as e:
                    logger.error("Durable webhook acceptance failed: %s", e)
                    return Response(content='{"status":"retry"}', status_code=503)

                accepted += 1
                stream_payload: dict[str, str] = {
                    "tenant_id": tenant_id,
                    "message_id": message_id,
                    "payload": json.dumps(event_payload),
                }
                try:
                    await get_redis().xadd("vaani:inbound_stream", cast(Any, stream_payload))
                except Exception as e:
                    # MongoDB is the queue of record; its scanner will recover this event.
                    logger.warning("Redis wake-up failed for %s: %s", message_id, e)

    status = "accepted" if accepted else "duplicate" if duplicates else "ignored"
    return Response(content=json.dumps({"status": status, "accepted": accepted}), status_code=200)

