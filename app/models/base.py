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

import importlib.util
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger(__name__)

_client: Any = None


def get_db() -> AsyncIOMotorDatabase[Any]:
    """Process-wide Motor client + `vaani` database handle."""
    global _client
    if _client is None:
        use_mock = False
        if settings.mongodb_uri == "mongodb://localhost:27017/vaani":
            use_mock = importlib.util.find_spec("mongomock_motor") is not None

        if use_mock:
            from mongomock_motor import AsyncMongoMockClient
            logger.info("Using mock MongoDB database client (mongomock-motor)")
            _client = AsyncMongoMockClient()
        else:
            _client = AsyncIOMotorClient(settings.mongodb_uri)

    db: AsyncIOMotorDatabase[Any]
    try:
        db = _client.get_default_database()
    except Exception:
        db = _client["vaani"]
    return db



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

    def _scoped(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return {**(query or {}), "tenant_id": self.tenant_id}

    async def find_one(
        self, filter: dict[str, Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any] | None:
        return await self._col.find_one(self._scoped(filter), *args, **kwargs)

    def find(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        return self._col.find(self._scoped(filter), *args, **kwargs)

    async def insert_one(self, document: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        doc_with_tenant = {**document, "tenant_id": self.tenant_id}
        return await self._col.insert_one(doc_with_tenant, *args, **kwargs)

    async def update_one(
        self, filter: dict[str, Any], update: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        return await self._col.update_one(self._scoped(filter), update, *args, **kwargs)

    async def find_one_and_update(
        self, filter: dict[str, Any], update: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        return await self._col.find_one_and_update(self._scoped(filter), update, *args, **kwargs)

    async def delete_many(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        return await self._col.delete_many(self._scoped(filter), *args, **kwargs)

    async def count_documents(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> int:
        return await self._col.count_documents(self._scoped(filter), *args, **kwargs)

