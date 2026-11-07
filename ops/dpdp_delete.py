"""Tenant-scoped, resumable patient erasure with a mandatory dry run."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.models.base import get_db
from app.privacy import identifier_hash
from bson import ObjectId


def _scrub(value: Any, needles: set[str]) -> Any:
    if isinstance(value, str):
        scrubbed = value
        for needle in needles:
            scrubbed = scrubbed.replace(needle, "[erased]")
        return scrubbed
    if isinstance(value, list):
        return [_scrub(item, needles) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item, needles) for key, item in value.items()}
    return value


async def _contact(tenant_id: str, contact_id: str) -> dict[str, Any] | None:
    candidates: list[Any] = [contact_id]
    if ObjectId.is_valid(contact_id):
        candidates.append(ObjectId(contact_id))
    matches = await get_db()["contacts"].find(
        {"tenant_id": tenant_id, "_id": {"$in": candidates}}
    ).to_list(length=2)
    if len(matches) > 1:
        raise ValueError("ambiguous contact id")
    return matches[0] if matches else None


async def erase_patient(
    tenant_id: str,
    contact_id: str,
    *,
    request_id: str,
    authorized_by: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Report or apply erasure without returning patient data as evidence."""
    if apply and not authorized_by:
        raise ValueError("authorized_by is required to apply erasure")
    db = get_db()
    contact = await _contact(tenant_id, contact_id)
    if not contact:
        previous = await db["erasure_requests"].find_one(
            {"tenant_id": tenant_id, "request_id": request_id, "status": "completed"}
        )
        return {
            "request_id": request_id,
            "status": "already_completed" if previous else "not_found",
            "counts": previous.get("counts", {}) if previous else {},
        }

    stored_contact_id = contact["_id"]
    identifiers = {
        str(stored_contact_id),
        str(contact.get("wa_id", "")),
        str(contact.get("phone", "")),
        str(contact.get("name", "")),
    } - {""}
    id_variants = [stored_contact_id, str(stored_contact_id)]
    conversations = await db["conversations"].find(
        {"tenant_id": tenant_id, "contact_id": {"$in": id_variants}}
    ).to_list(length=None)
    conversation_ids = [conversation["_id"] for conversation in conversations]
    booking_docs = await db["bookings"].find(
        {"tenant_id": tenant_id, "contact_id": {"$in": id_variants}}
    ).to_list(length=None)
    booking_ids = [booking["_id"] for booking in booking_docs]
    identifiers.update(str(booking_id) for booking_id in booking_ids)

    message_docs = await db["messages"].find({"tenant_id": tenant_id}).to_list(length=None)
    message_ids = [
        message["_id"]
        for message in message_docs
        if message.get("conversation_id") in conversation_ids
        or any(needle in json.dumps(message, default=str) for needle in identifiers)
    ]
    payment_docs = await db["payments"].find(
        {
            "tenant_id": tenant_id,
            "$or": [
                {"contact_id": {"$in": id_variants}},
                {"booking_id": {"$in": booking_ids + [str(item) for item in booking_ids]}},
            ],
        }
    ).to_list(length=None)
    audit_docs = await db["audit_log"].find({"tenant_id": tenant_id}).to_list(length=None)
    matching_audit = [
        document
        for document in audit_docs
        if any(needle in json.dumps(document, default=str) for needle in identifiers)
        or document.get("conversation_id") in conversation_ids
    ]
    outbound_docs = await db["outbound_intents"].find(
        {"tenant_id": tenant_id}
    ).to_list(length=None)
    matching_outbound = [
        document
        for document in outbound_docs
        if any(needle in json.dumps(document, default=str) for needle in identifiers)
    ]
    waitlist_count = await db["waitlist"].count_documents(
        {"tenant_id": tenant_id, "contact_id": {"$in": id_variants}}
    )
    escalation_count = await db["escalations"].count_documents(
        {"tenant_id": tenant_id, "conversation_id": {"$in": conversation_ids}}
    )
    counts = {
        "contacts_delete": 1,
        "conversations_delete": len(conversations),
        "messages_delete": len(message_ids),
        "bookings_delete": len(booking_docs),
        "waitlist_delete": waitlist_count,
        "escalations_delete": escalation_count,
        "payments_pseudonymize": len(payment_docs),
        "audit_pseudonymize": len(matching_audit),
        "outbound_suppress": len(matching_outbound),
    }
    report = {
        "request_id": request_id,
        "status": "dry_run" if not apply else "completed",
        "counts": counts,
        "retained_exceptions": ["payments", "audit_log", "erasure_suppression"],
    }
    if not apply:
        return report

    now = datetime.now(UTC).replace(tzinfo=None)
    contact_hash = identifier_hash(tenant_id, str(stored_contact_id))
    await db["erasure_requests"].update_one(
        {"tenant_id": tenant_id, "request_id": request_id},
        {
            "$set": {
                "status": "running",
                "contact_hash": contact_hash,
                "authorized_by": authorized_by,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    await db["erasure_suppression"].update_one(
        {"tenant_id": tenant_id, "contact_hash": contact_hash},
        {
            "$set": {
                "identifier_hashes": sorted(
                    identifier_hash(tenant_id, item) for item in identifiers
                ),
                "request_id": request_id,
                "created_at": now,
            }
        },
        upsert=True,
    )

    for document in payment_docs:
        scrubbed = _scrub(document, identifiers)
        scrubbed["contact_id"] = "[erased]"
        await db["payments"].replace_one(
            {"_id": document["_id"], "tenant_id": tenant_id}, scrubbed
        )
    for document in matching_audit:
        scrubbed = _scrub(document, identifiers)
        scrubbed.pop("conversation_id", None)
        await db["audit_log"].replace_one(
            {"_id": document["_id"], "tenant_id": tenant_id}, scrubbed
        )
    for document in matching_outbound:
        await db["outbound_intents"].update_one(
            {"_id": document["_id"], "tenant_id": tenant_id},
            {
                "$set": {"state": "suppressed", "to": "[erased]", "suppressed_at": now},
                "$unset": {"last_error": ""},
            },
        )

    if message_ids:
        await db["messages"].delete_many(
            {"tenant_id": tenant_id, "_id": {"$in": message_ids}}
        )
    if conversation_ids:
        await db["escalations"].delete_many(
            {"tenant_id": tenant_id, "conversation_id": {"$in": conversation_ids}}
        )
        await db["conversations"].delete_many(
            {"tenant_id": tenant_id, "_id": {"$in": conversation_ids}}
        )
    if booking_ids:
        await db["bookings"].delete_many(
            {"tenant_id": tenant_id, "_id": {"$in": booking_ids}}
        )
    await db["waitlist"].delete_many(
        {"tenant_id": tenant_id, "contact_id": {"$in": id_variants}}
    )
    await db["contacts"].delete_one({"tenant_id": tenant_id, "_id": stored_contact_id})
    await db["erasure_requests"].update_one(
        {"tenant_id": tenant_id, "request_id": request_id},
        {"$set": {"status": "completed", "counts": counts, "completed_at": now}},
    )
    return report


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--contact", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--authorized-by")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = await erase_patient(
        args.tenant,
        args.contact,
        request_id=args.request_id,
        authorized_by=args.authorized_by,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
