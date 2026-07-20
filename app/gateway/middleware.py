"""Gateway middleware: signature verify, tenant resolution, idempotency.

Applied to inbound webhooks before anything is enqueued (TRD §5.1, ADR-04).
  - Meta signature: verify X-Hub-Signature-256 against META_APP_SECRET.
  - Tenant resolution: inbound wa_number -> tenant_id.
  - Idempotency: Redis SETNX on message_id, 24h TTL — duplicate delivery must
    produce exactly one processed message (Week 3, task 3.2).
"""

from __future__ import annotations

import hashlib
import hmac
import logging

import redis.asyncio as redis

from app.config import settings
from app.models.collections import Messages, Tenants

logger = logging.getLogger(__name__)
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        # socket_timeout must exceed the largest BLOCK duration used by any caller
        # (the inbound worker's xreadgroup block=5000ms) — otherwise the client's
        # own read timeout races the server's blocking window and fires first.
        _redis_client = redis.from_url(
            settings.redis_url, decode_responses=True, socket_timeout=30
        )
    return _redis_client


def verify_meta_signature(body: bytes, signature_header: str | None) -> bool:
    """HMAC-SHA256 body check against the app secret."""
    if not settings.meta_app_secret:
        if settings.app_env in ("staging", "prod"):
            return False
        # If no secret is configured, allow in dev/testing environments
        return True
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    
    expected_signature = signature_header[7:]
    computed_signature = hmac.new(
        key=settings.meta_app_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, expected_signature)


async def resolve_tenant(wa_number: str) -> str:
    """Map an inbound business number to its tenant_id."""
    tenant = await Tenants.find_by_wa_number(wa_number)
    if not tenant:
        raise ValueError(f"Unknown wa_number: {wa_number}")
    return str(tenant["_id"])


async def claim_message(message_id: str) -> bool:
    """Check MongoDB then Redis SETNX (24h TTL). Returns True on first sighting."""
    # 1. First, check MongoDB to see if we've ever processed/seen this message ID before.
    # This prevents reprocessing even if Redis keys have expired (solving 24h expiry).
    try:
        if await Messages.seen_unscoped(message_id):
            return False
    except Exception as e:
        logger.warning("MongoDB read failed during idempotency check: %s", e)

    # 2. Try Redis SETNX for lock/concurrency control
    try:
        r = get_redis()
        key = f"msg_id:{message_id}"
        # set with nx=True and ex=24h returns True if key was set, None otherwise
        is_new = await r.set(key, "1", ex=24 * 3600, nx=True)
        if is_new is None:
            return False
    except Exception as e:
        logger.warning("Redis is down, falling back to MongoDB for reservation: %s", e)

    # 3. Reserve the ID with a placeholder to prevent concurrent reprocessing on retries
    try:
        await Messages.reserve_placeholder_unscoped(message_id)
        return True
    except Exception as e:
        logger.error("MongoDB reservation failed: %s", e)
        # DB also failing: return True so we don't drop the message
        return True

