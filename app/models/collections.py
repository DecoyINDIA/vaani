"""Per-collection accessors (TRD §3 data model).

One class per MongoDB collection, each a ``TenantScoped`` subclass. Stubs for
now — method bodies land as the walking skeleton is filled in (06-engineering-plan
Week 3, task 3.4). Index creation lives in `ensure_indexes()`.
"""

from __future__ import annotations

from app.models.base import TenantScoped, get_db


class Tenants(TenantScoped):
    collection = "tenants"


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
    _ = get_db()
    raise NotImplementedError("index creation — 06-engineering-plan task 3.4")
