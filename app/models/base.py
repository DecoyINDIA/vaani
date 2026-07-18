"""Data-access foundation.

Non-negotiable rule (06-engineering-plan §0, rule 1): `tenant_id` is an explicit,
required first argument on EVERY accessor. No ambient tenant context, no default.
A CI grep forbids raw `db[...].find/insert/update/delete` anywhere outside this
package, so all collection access must funnel through accessors defined here.

Collections and their shapes are specified in TRD §3. Every collection is
compound-indexed on (tenant_id, ...); `slots` is unique on
(tenant_id, practitioner_id, start).
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_db() -> AsyncIOMotorDatabase:
    """Process-wide Motor client + `vaani` database handle."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client.get_default_database()


class TenantScoped:
    """Base for per-collection accessors.

    Subclasses expose typed methods (find_one, insert, ...) that inject
    ``tenant_id`` into every filter and document. Consumers never build raw
    Mongo filters — they call these methods with tenant_id as the first arg.
    """

    collection: str

    def __init__(self, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required on every accessor — no default permitted")
        self.tenant_id = tenant_id
        self._col = get_db()[self.collection]

    def _scoped(self, query: dict | None = None) -> dict:
        return {**(query or {}), "tenant_id": self.tenant_id}
