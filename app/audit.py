"""Append-only audit — the single choke point for every side-effect.

Non-negotiable rule (06-engineering-plan §0, rule 2): every outbound message and
every tool call goes through here. No direct sends anywhere else. A transcript
must be fully reconstructable from the audit log alone (Week 5, task 5.4).

Writes to the `audit_log` collection (TRD §3): append-only, TTL 90d default.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.config import settings
from app.models.collections import AuditLog

logger = logging.getLogger(__name__)

Actor = Literal["agent", "user", "owner", "system"]

_FORBIDDEN_ALERT_KEYS = frozenset(
    {
        "phone",
        "wa_id",
        "caller_phone",
        "patient_name",
        "name",
        "text",
        "body",
        "transcript",
        "payload",
        "email",
    }
)


async def _dispatch_operational_alert(tenant_id: str, payload: dict[str, Any]) -> None:
    destination = settings.alerts_destination_url
    if not destination:
        return
    sanitized = {k: v for k, v in payload.items() if k not in _FORBIDDEN_ALERT_KEYS}
    body = {
        "tenant_id": tenant_id,
        "event_type": "operational_alert",
        "kind": str(sanitized.get("kind", "unknown")),
        "details": sanitized,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(destination, json=body)
    except Exception as exc:
        logger.warning("Failed to dispatch operational alert to %s: %s", destination, exc)


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
        "ts": datetime.now(UTC).replace(tzinfo=None),
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

    if event_type == "operational_alert":
        await _dispatch_operational_alert(tenant_id, payload)
