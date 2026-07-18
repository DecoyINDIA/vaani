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
from app.models.base import get_db
from app.models.collections import Tenants

logger = logging.getLogger(__name__)
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def verify_meta_signature(body: bytes, signature_header: str | None) -> bool:
    """HMAC-SHA256 body check against the app secret."""
    if not settings.meta_app_secret:
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
    """Redis SETNX with 24h TTL. Returns True if this is the first sighting."""
    # 1. Try Redis
    try:
        r = get_redis()
        key = f"msg_id:{message_id}"
        # set with nx=True and ex=24h returns True if key was set, None otherwise
        is_new = await r.set(key, "1", ex=24 * 3600, nx=True)
        if is_new is not None:
            return bool(is_new)
    except Exception as e:
        logger.warning("Redis is down, falling back to MongoDB for idempotency: %s", e)

    # 2. Fallback to MongoDB
    try:
        db = get_db()
        existing = await db["messages"].find_one({"_id": message_id})
        if existing:
            return False
        
        # We write a placeholder to prevent concurrent processing races in case of multiple retries
        # Note: tenant_id isn't resolved globally here, but we can store it with a dummy or minimal info
        # to reserve the ID. Or we can just return True. To be safe, let's insert a minimal placeholder.
        await db["messages"].insert_one({
            "_id": message_id,
            "direction": "inbound",
            "type": "placeholder",
            "ts": get_db().client.loop.time() if hasattr(get_db().client, "loop") else 0
        })
        return True
    except Exception as e:
        logger.error("MongoDB idempotency fallback failed: %s", e)
        # If database is also failing, return True so we don't drop the message, but it will fail downstream
        return True

