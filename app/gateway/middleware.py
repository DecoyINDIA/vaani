"""Gateway middleware: signature verify, tenant resolution, idempotency.

Applied to inbound webhooks before anything is enqueued (TRD §5.1, ADR-04).
  - Meta signature: verify X-Hub-Signature-256 against META_APP_SECRET.
  - Tenant resolution: inbound wa_number -> tenant_id.
  - Idempotency: Redis SETNX on message_id, 24h TTL — duplicate delivery must
    produce exactly one processed message (Week 3, task 3.2).
"""

from __future__ import annotations


def verify_meta_signature(body: bytes, signature_header: str | None) -> bool:
    """HMAC-SHA256 body check against the app secret."""
    raise NotImplementedError("Meta signature verify — 06-engineering-plan task 3.2")


async def resolve_tenant(wa_number: str) -> str:
    """Map an inbound business number to its tenant_id."""
    raise NotImplementedError("tenant resolution — 06-engineering-plan task 3.2")


async def claim_message(message_id: str) -> bool:
    """Redis SETNX with 24h TTL. Returns True if this is the first sighting."""
    raise NotImplementedError("idempotency claim — 06-engineering-plan task 3.2")
