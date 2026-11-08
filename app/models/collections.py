"""Per-collection accessors (TRD §3 data model).

One class per MongoDB collection, each a ``TenantScoped`` subclass. Stubs for
now — method bodies land as the walking skeleton is filled in (06-engineering-plan
Week 3, task 3.4). Index creation lives in `ensure_indexes()`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pymongo import ReturnDocument

from app.models.base import TenantScoped, get_db


class Tenants(TenantScoped):
    collection = "tenants"

    def __init__(self, tenant_id: str = "SYSTEM") -> None:
        super().__init__(tenant_id)

    @classmethod
    async def find_by_id(cls, tenant_id: str) -> dict[str, Any] | None:
        return await get_db()[cls.collection].find_one({"_id": tenant_id})

    @classmethod
    async def update_tenant_plan(
        cls, tenant_id: str, plan: str, billing_status: str
    ) -> None:
        await get_db()[cls.collection].update_one(
            {"_id": tenant_id},
            {"$set": {"plan": plan, "billing_status": billing_status}},
        )

    @classmethod
    async def find_by_wa_number(cls, wa_number: str) -> dict[str, Any] | None:
        return await get_db()[cls.collection].find_one({"wa_number": wa_number})

    @classmethod
    async def find_by_voice_number(cls, voice_number: str) -> dict[str, Any] | None:
        return await get_db()[cls.collection].find_one({"voice_number": voice_number})

    @classmethod
    async def all(cls) -> list[dict[str, Any]]:
        """Cross-tenant scan for platform workers (reminders, weekly summaries)."""
        return [doc async for doc in get_db()[cls.collection].find({})]



class Users(TenantScoped):
    collection = "users"


class Contacts(TenantScoped):
    collection = "contacts"


class Conversations(TenantScoped):
    collection = "conversations"


class Messages(TenantScoped):
    collection = "messages"

    @classmethod
    async def seen_unscoped(cls, message_id: str) -> bool:
        """Idempotency check before tenant resolution — has this id been sighted?"""
        return await get_db()[cls.collection].find_one({"_id": message_id}) is not None

    @classmethod
    async def accept_inbound_unscoped(
        cls, message_id: str, tenant_id: str, payload: dict[str, Any]
    ) -> None:
        """Durably accept the complete provider event; duplicate IDs fail the insert."""
        await get_db()[cls.collection].insert_one(
            {
                "_id": message_id,
                "tenant_id": tenant_id,
                "direction": "inbound",
                "type": "inbound_event",
                "status": "queued",
                "payload": payload,
                "attempts": 0,
                "accepted_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )

    @classmethod
    async def upsert_fallback_message_unscoped(
        cls, tenant_id: str, message_id: str, document: dict[str, Any]
    ) -> None:
        """Upsert a message when Redis is down and we are falling back to MongoDB."""
        doc_with_tenant = {**document, "_id": message_id, "tenant_id": tenant_id}
        await get_db()[cls.collection].replace_one(
            {"_id": message_id},
            doc_with_tenant,
            upsert=True
        )

    @classmethod
    async def upsert_message_unscoped(
        cls, message_id: str, tenant_id: str, document: dict[str, Any]
    ) -> None:
        """Record the transcript without discarding in-flight recovery metadata."""
        await get_db()[cls.collection].update_one(
            {"_id": message_id},
            {"$set": {**document, "tenant_id": tenant_id}},
            upsert=True
        )

    @classmethod
    async def acquire_work_unscoped(cls, message_id: str) -> dict[str, Any] | None:
        """Atomically lease queued or abandoned work to one worker for 60 seconds."""
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await get_db()[cls.collection].find_one_and_update(
            {
                "_id": message_id,
                "$or": [
                    {"status": "queued"},
                    {"status": "processing", "lease_expires_at": {"$lte": now}},
                ],
            },
            {
                "$set": {"status": "processing", "lease_expires_at": now + timedelta(seconds=60)},
                "$inc": {"attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return cast(dict[str, Any] | None, result)

    @classmethod
    async def release_work_unscoped(cls, message_id: str, reason: str) -> None:
        await get_db()[cls.collection].update_one(
            {"_id": message_id, "status": "processing"},
            {
                "$set": {"status": "queued", "last_error": reason},
                "$unset": {"lease_expires_at": ""},
            },
        )

    @classmethod
    async def mark_completed_unscoped(cls, message_id: str) -> None:
        """Remove queue data only after all event processing has completed."""
        await get_db()[cls.collection].update_one(
            {"_id": message_id, "status": "processing"},
            {
                "$set": {"processed_at": datetime.now(UTC).replace(tzinfo=None)},
                "$unset": {
                    "status": "",
                    "payload": "",
                    "lease_expires_at": "",
                    "last_error": "",
                },
            },
        )

    @classmethod
    async def find_queued_unscoped(cls) -> list[dict[str, Any]]:
        """Find queued and expired leased work across all tenants."""
        now = datetime.now(UTC).replace(tzinfo=None)
        query = {
            "$or": [
                {"status": "queued"},
                {"status": "processing", "lease_expires_at": {"$lte": now}},
            ]
        }
        return [doc async for doc in get_db()[cls.collection].find(query)]

    @classmethod
    async def mark_failed_unscoped(cls, message_id: str, reason: str) -> None:
        """Mark a message as failed (dead-letter equivalent)."""
        await get_db()[cls.collection].update_one(
            {"_id": message_id},
            {"$set": {"status": "failed", "fail_reason": reason}}
        )

    @classmethod
    async def increment_retries_unscoped(cls, message_id: str) -> None:
        """Increment retry count on a queued message."""
        await get_db()[cls.collection].update_one(
            {"_id": message_id},
            {"$inc": {"retries": 1}}
        )


class KbEntries(TenantScoped):
    collection = "kb_entries"


class Practitioners(TenantScoped):
    collection = "practitioners"


class Slots(TenantScoped):
    collection = "slots"


class Bookings(TenantScoped):
    collection = "bookings"


class Payments(TenantScoped):
    collection = "payments"

    @classmethod
    async def find_by_link_id_unscoped(cls, rzp_link_id: str) -> dict[str, Any] | None:
        return await get_db()[cls.collection].find_one({"rzp_link_id": rzp_link_id})


class OutboundIntents(TenantScoped):
    collection = "outbound_intents"


class Escalations(TenantScoped):
    collection = "escalations"


class Waitlist(TenantScoped):
    collection = "waitlist"


class AuditLog(TenantScoped):
    collection = "audit_log"


class UsageMeters(TenantScoped):
    collection = "usage_meters"


class UsageEvents(TenantScoped):
    collection = "usage_events"


class Invoices(TenantScoped):
    collection = "invoices"


class BillingSubscriptions(TenantScoped):
    collection = "billing_subscriptions"


class VoiceGrants(TenantScoped):
    collection = "voice_grants"


class AuthSessions(TenantScoped):
    collection = "auth_sessions"


class AuthRateLimits(TenantScoped):
    collection = "auth_rate_limits"


class JobRuns(TenantScoped):
    collection = "job_runs"


async def ensure_indexes() -> None:
    """Create compound (tenant_id, ...) indexes + the slots uniqueness constraint.

    Called on startup / by seed_tenant.py. TRD §3: slots unique on
    (tenant_id, practitioner_id, start); audit_log TTL 90d; media purge 30d.
    """
    db = get_db()
    
    # 1. Tenants indexes
    await db["tenants"].create_index("wa_number")
    await db["tenants"].create_index("voice_number")

    # 2. Users indexes
    await db["users"].create_index([("tenant_id", 1), ("phone", 1)])

    # 3. Contacts indexes
    await db["contacts"].create_index([("tenant_id", 1), ("wa_id", 1)])
    await db["contacts"].create_index([("tenant_id", 1), ("phone", 1)])

    # 4. Conversations indexes
    await db["conversations"].create_index([("tenant_id", 1), ("contact_id", 1)])
    await db["conversations"].create_index([("tenant_id", 1), ("state", 1)])

    # 5. Messages indexes
    await db["messages"].create_index([("tenant_id", 1), ("conversation_id", 1)])
    await db["messages"].create_index(
        [("tenant_id", 1), ("staff_request_id", 1)],
        unique=True,
        partialFilterExpression={"staff_request_id": {"$type": "string"}},
    )
    await db["messages"].create_index(
        [("tenant_id", 1), ("operation_key", 1)],
        unique=True,
        partialFilterExpression={"operation_key": {"$type": "string"}},
    )

    # 6. KbEntries indexes
    await db["kb_entries"].create_index([("tenant_id", 1), ("key", 1)])

    # 7. Practitioners indexes
    await db["practitioners"].create_index([("tenant_id", 1)])

    # 8. Slots uniqueness constraint
    await db["slots"].create_index(
        [("tenant_id", 1), ("practitioner_id", 1), ("start", 1)],
        unique=True
    )

    # 9. Bookings indexes
    await db["bookings"].create_index([("tenant_id", 1), ("slot_id", 1)])
    await db["bookings"].create_index(
        [("tenant_id", 1), ("request_id", 1)],
        unique=True,
        partialFilterExpression={"request_id": {"$type": "string"}},
    )

    # 10. Payments indexes
    await db["payments"].create_index([("tenant_id", 1), ("booking_id", 1)])
    await db["payments"].create_index(
        [("tenant_id", 1), ("request_id", 1)],
        unique=True,
        partialFilterExpression={"request_id": {"$type": "string"}},
    )

    # 11. Escalations indexes
    await db["escalations"].create_index([("tenant_id", 1), ("conversation_id", 1)])
    await db["escalations"].create_index(
        [("tenant_id", 1), ("conversation_id", 1), ("status", 1)], unique=True
    )

    await db["outbound_intents"].create_index(
        [("tenant_id", 1), ("operation_key", 1)], unique=True
    )
    await db["job_runs"].create_index(
        [("tenant_id", 1), ("job", 1), ("key", 1)], unique=True
    )
    await db["outbound_intents"].create_index(
        [("tenant_id", 1), ("provider_message_id", 1)],
        partialFilterExpression={"provider_message_id": {"$type": "string"}},
    )

    # 12. AuditLog indexes (with 90-day TTL)
    await db["audit_log"].create_index([("tenant_id", 1)])
    await db["audit_log"].create_index(
        [("tenant_id", 1), ("operation_key", 1)],
        unique=True,
        partialFilterExpression={"operation_key": {"$type": "string"}},
    )
    await db["audit_log"].create_index("ts", expireAfterSeconds=90 * 24 * 3600)

    # 13. UsageMeters indexes
    await db["usage_meters"].create_index([("tenant_id", 1), ("period", 1)], unique=True)
    await db["usage_events"].create_index(
        [("tenant_id", 1), ("event_id", 1)], unique=True
    )
    await db["usage_events"].create_index([("tenant_id", 1), ("period", 1)])
    await db["invoices"].create_index(
        [("tenant_id", 1), ("period", 1)], unique=True
    )
    await db["billing_subscriptions"].create_index(
        [("tenant_id", 1), ("provider_subscription_id", 1)], unique=True
    )
    await db["voice_grants"].create_index(
        [("tenant_id", 1), ("call_sid", 1)], unique=True
    )
    await db["voice_grants"].create_index("expires_at", expireAfterSeconds=0)
    await db["auth_sessions"].create_index(
        [("tenant_id", 1), ("session_id", 1)], unique=True
    )
    await db["auth_sessions"].create_index("expires_at", expireAfterSeconds=0)
    await db["auth_rate_limits"].create_index(
        [("tenant_id", 1), ("kind", 1), ("subject_hash", 1), ("window", 1)],
        unique=True,
    )
    await db["auth_rate_limits"].create_index("expires_at", expireAfterSeconds=0)

    # 14. Waitlist indexes
    await db["waitlist"].create_index([("tenant_id", 1), ("practitioner_id", 1), ("date", 1)])

