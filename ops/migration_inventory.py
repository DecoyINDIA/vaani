"""Read-only, redacted inventory required before production data backfills.

Usage: ``python -m ops.migration_inventory``. The command prints counts and
hashed record references only; it never emits patient content or mutates data.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.models.base import get_db
from bson import ObjectId

COLLECTIONS = (
    "tenants",
    "users",
    "contacts",
    "conversations",
    "messages",
    "kb_entries",
    "practitioners",
    "slots",
    "bookings",
    "payments",
    "escalations",
    "waitlist",
    "outbound_intents",
    "job_runs",
    "usage_events",
    "invoices",
    "billing_subscriptions",
    "voice_grants",
    "auth_sessions",
)

REFERENCES = (
    ("conversations", "contact_id", "contacts"),
    ("messages", "conversation_id", "conversations"),
    ("bookings", "contact_id", "contacts"),
    ("bookings", "slot_id", "slots"),
    ("payments", "booking_id", "bookings"),
    ("escalations", "conversation_id", "conversations"),
    ("waitlist", "contact_id", "contacts"),
)


def _tenant(collection: str, document: dict[str, Any]) -> str:
    value = document.get("_id") if collection == "tenants" else document.get("tenant_id")
    return str(value) if value is not None else "<missing>"


def _type_name(value: Any) -> str:
    return "objectid" if isinstance(value, ObjectId) else type(value).__name__


def _sample(*parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts).encode()
    return hashlib.sha256(raw).hexdigest()[:12]


async def build_inventory() -> dict[str, Any]:
    """Inspect migration hazards without changing or disclosing stored records."""
    db = get_db()
    documents: dict[str, list[dict[str, Any]]] = {
        name: [document async for document in db[name].find({})] for name in COLLECTIONS
    }
    counts: dict[str, dict[str, int]] = {}
    id_types: dict[str, dict[str, int]] = {}
    target_ids: dict[str, dict[str, set[str]]] = {}
    ambiguous_ids: dict[str, list[dict[str, str]]] = {}

    for collection, items in documents.items():
        by_tenant = Counter(_tenant(collection, item) for item in items)
        counts[collection] = dict(sorted(by_tenant.items()))
        id_types[collection] = dict(
            sorted(Counter(_type_name(item.get("_id")) for item in items).items())
        )
        normalized: dict[str, set[str]] = defaultdict(set)
        by_tenant_ids: dict[str, set[str]] = defaultdict(set)
        for item in items:
            tenant_id = _tenant(collection, item)
            value = item.get("_id")
            normalized[f"{tenant_id}\x1f{value}"].add(_type_name(value))
            by_tenant_ids[tenant_id].add(str(value))
        target_ids[collection] = by_tenant_ids
        ambiguous_ids[collection] = [
            {"sample": _sample(collection, key), "types": ",".join(sorted(types))}
            for key, types in sorted(normalized.items())
            if len(types) > 1
        ][:20]

    reference_types: dict[str, dict[str, int]] = {}
    orphan_references: dict[str, dict[str, Any]] = {}
    for source, field, target in REFERENCES:
        key = f"{source}.{field}->{target}"
        values = [item for item in documents[source] if item.get(field) is not None]
        reference_types[key] = dict(
            sorted(Counter(_type_name(item[field]) for item in values).items())
        )
        orphans = [
            item
            for item in values
            if str(item[field]) not in target_ids[target].get(_tenant(source, item), set())
        ]
        orphan_references[key] = {
            "count": len(orphans),
            "samples": [
                _sample(_tenant(source, item), source, item.get("_id"), field, item[field])
                for item in orphans[:20]
            ],
        }

    duplicate_contacts: dict[str, int] = {}
    for field in ("wa_id", "phone"):
        groups = Counter(
            (_tenant("contacts", item), str(item[field]))
            for item in documents["contacts"]
            if item.get(field)
        )
        duplicate_contacts[field] = sum(1 for count in groups.values() if count > 1)

    active_groups = Counter(
        (_tenant("conversations", item), str(item.get("contact_id")))
        for item in documents["conversations"]
        if item.get("state") in {"bot", "human", "open"} and item.get("contact_id") is not None
    )
    duplicate_active_conversations = sum(1 for count in active_groups.values() if count > 1)

    timestamp_types: Counter[str] = Counter()
    for collection, items in documents.items():
        for item in items:
            for field, value in item.items():
                if (
                    field == "ts"
                    or field.endswith("_at")
                    or field in {"start", "end", "hold_expiry"}
                ):
                    if isinstance(value, datetime):
                        kind = "aware" if value.tzinfo is not None else "naive"
                    else:
                        kind = f"non_datetime:{_type_name(value)}"
                    timestamp_types[f"{collection}.{field}:{kind}"] += 1

    tenant_plans = Counter(str(item.get("plan", "<missing>")) for item in documents["tenants"])
    provider_plans = Counter(
        str(item.get("provider_plan_id", "<missing>"))
        for item in documents["billing_subscriptions"]
    )

    return {
        "read_only": True,
        "redaction": "record samples are irreversible 12-character SHA-256 prefixes",
        "counts_by_tenant": counts,
        "id_types": id_types,
        "ambiguous_ids": ambiguous_ids,
        "reference_types": reference_types,
        "orphan_references": orphan_references,
        "duplicate_contact_groups": duplicate_contacts,
        "duplicate_active_conversation_groups": duplicate_active_conversations,
        "legacy_open_conversations": sum(
            1 for item in documents["conversations"] if item.get("state") == "open"
        ),
        "queued_or_placeholder_messages": sum(
            1
            for item in documents["messages"]
            if item.get("status") == "queued" or item.get("type") == "placeholder"
        ),
        "slot_ownership": {
            "held_without_owner": sum(
                1
                for item in documents["slots"]
                if item.get("status") == "held" and not item.get("hold_owner")
            ),
            "booked_without_booking_id": sum(
                1
                for item in documents["slots"]
                if item.get("status") == "booked" and not item.get("booking_id")
            ),
        },
        "timestamp_provenance": dict(sorted(timestamp_types.items())),
        "plan_values": {
            "tenant_plan": dict(sorted(tenant_plans.items())),
            "provider_plan_id": dict(sorted(provider_plans.items())),
        },
    }


async def _main() -> None:
    print(json.dumps(await build_inventory(), indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
