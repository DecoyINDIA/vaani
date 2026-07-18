"""Per-collection accessors (TRD §3 data model).

One class per MongoDB collection, each a ``TenantScoped`` subclass. Stubs for
now — method bodies land as the walking skeleton is filled in (06-engineering-plan
Week 3, task 3.4). Index creation lives in `ensure_indexes()`.
"""

from __future__ import annotations

from app.models.base import TenantScoped, get_db


class Tenants(TenantScoped):
    collection = "tenants"

    def __init__(self, tenant_id: str = "SYSTEM") -> None:
        super().__init__(tenant_id)

    @classmethod
    async def find_by_wa_number(cls, wa_number: str) -> dict | None:
        return await get_db()[cls.collection].find_one({"wa_number": wa_number})



class Users(TenantScoped):
    collection = "users"


class Contacts(TenantScoped):
    collection = "contacts"


class Conversations(TenantScoped):
    collection = "conversations"


class Messages(TenantScoped):
    collection = "messages"


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


class Escalations(TenantScoped):
    collection = "escalations"


class AuditLog(TenantScoped):
    collection = "audit_log"


class UsageMeters(TenantScoped):
    collection = "usage_meters"


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

    # 10. Payments indexes
    await db["payments"].create_index([("tenant_id", 1), ("booking_id", 1)])

    # 11. Escalations indexes
    await db["escalations"].create_index([("tenant_id", 1), ("conversation_id", 1)])

    # 12. AuditLog indexes (with 90-day TTL)
    await db["audit_log"].create_index([("tenant_id", 1)])
    await db["audit_log"].create_index("ts", expireAfterSeconds=90 * 24 * 3600)

    # 13. UsageMeters indexes
    await db["usage_meters"].create_index([("tenant_id", 1)])

