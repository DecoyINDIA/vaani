"""Hashed erasure suppression checks shared by ingress and delivery."""

from __future__ import annotations

import hashlib

from app.models.base import get_db


def identifier_hash(tenant_id: str, value: str) -> str:
    return hashlib.sha256(f"{tenant_id}:{value}".encode()).hexdigest()


async def is_suppressed(tenant_id: str, value: str) -> bool:
    return await get_db()["erasure_suppression"].find_one(
        {"tenant_id": tenant_id, "identifier_hashes": identifier_hash(tenant_id, value)}
    ) is not None
