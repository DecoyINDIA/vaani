"""Append-only audit — the single choke point for every side-effect.

Non-negotiable rule (06-engineering-plan §0, rule 2): every outbound message and
every tool call goes through here. No direct sends anywhere else. A transcript
must be fully reconstructable from the audit log alone (Week 5, task 5.4).

Writes to the `audit_log` collection (TRD §3): append-only, TTL 90d default.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from app.models.collections import AuditLog

Actor = Literal["agent", "user", "owner", "system"]


async def record(
    tenant_id: str,
    *,
    actor: Actor,
    event_type: str,
    payload: dict[str, Any],
    conversation_id: str | None = None,
    operation_key: str | None = None,
) -> None:
    """Append one immutable audit entry, or retain the first keyed replay."""
    audit_entry = {
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
        "ts": datetime.now(UTC).replace(tzinfo=None)
    }
    if conversation_id:
        audit_entry["conversation_id"] = conversation_id

    accessor = AuditLog(tenant_id)
    if operation_key:
        audit_entry["operation_key"] = operation_key
        await accessor.update_one(
            {"operation_key": operation_key},
            {"$setOnInsert": audit_entry},
            upsert=True,
        )
    else:
        await accessor.insert_one(audit_entry)
