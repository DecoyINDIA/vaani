"""Dry-run-first, resumable data backfill and normalization.

Usage:
  python -m ops.resumable_migration --dry-run
  python -m ops.resumable_migration --apply --confirm MIGRATE \
      [--tenant <tenant_id>] [--batch-size <N>]

This script normalizes:
1. Legacy conversation states ('open' -> 'bot')
2. References across collections (str <-> ObjectId) matching canonical target _id types
3. Expired slot holds and slot-booking ownership
4. Unambiguous ISO string timestamps to naive UTC datetimes
5. Reporting ambiguous collisions, orphans, and stranded messages for operator review
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models.base import get_db
from bson import ObjectId

RELATIONSHIPS = (
    ("conversations", "contact_id", "contacts"),
    ("messages", "conversation_id", "conversations"),
    ("bookings", "contact_id", "contacts"),
    ("bookings", "slot_id", "slots"),
    ("payments", "booking_id", "bookings"),
    ("escalations", "conversation_id", "conversations"),
    ("waitlist", "contact_id", "contacts"),
)

TIMESTAMP_FIELDS: dict[str, tuple[str, ...]] = {
    "conversations": ("started_at", "updated_at", "closed_at"),
    "messages": ("ts", "created_at"),
    "slots": ("start", "end", "hold_expiry", "created_at"),
    "bookings": ("created_at", "updated_at"),
    "payments": ("created_at", "updated_at"),
    "outbound_intents": ("created_at", "updated_at", "next_attempt_at"),
    "usage_events": ("created_at",),
}


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


async def run_migration(
    *,
    tenant_id: str | None = None,
    apply: bool = False,
    batch_size: int = 1000,
) -> dict[str, Any]:
    db = get_db()
    scope = {"tenant_id": tenant_id} if tenant_id else {}

    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "tenant_id": tenant_id or "all",
        "started_at": datetime.now(UTC).isoformat(),
        "conversation_states_normalized": 0,
        "references_normalized": defaultdict(int),
        "expired_holds_released": 0,
        "slot_ownership_reconciled": 0,
        "timestamps_normalized": defaultdict(int),
        "operator_review_required": {
            "ambiguous_collisions": [],
            "orphan_references": [],
            "stranded_messages": 0,
            "unowned_booked_slots": 0,
        },
    }

    # ---------------------------------------------------------
    # Stage 1: Legacy conversation state normalization (open -> bot)
    # ---------------------------------------------------------
    conv_query = {**scope, "state": "open"}
    open_convs = await db["conversations"].count_documents(conv_query)
    report["conversation_states_normalized"] = open_convs
    if apply and open_convs > 0:
        await db["conversations"].update_many(conv_query, {"$set": {"state": "bot"}})

    # ---------------------------------------------------------
    # Stage 2: Reference normalization across relationships
    # ---------------------------------------------------------
    for source_col, ref_field, target_col in RELATIONSHIPS:
        key = f"{source_col}.{ref_field}->{target_col}"
        source_cursor = db[source_col].find(
            {**scope, ref_field: {"$ne": None}},
            projection={"_id": 1, "tenant_id": 1, ref_field: 1},
        )
        candidates_to_update: list[tuple[Any, str, Any, Any]] = []

        async for doc in source_cursor:
            doc_tenant = doc.get("tenant_id")
            ref_val = doc.get(ref_field)
            if not doc_tenant or ref_val is None:
                continue

            ref_str = str(ref_val)
            lookup_candidates: list[Any] = [ref_val]
            if isinstance(ref_val, str) and ObjectId.is_valid(ref_val):
                lookup_candidates.append(ObjectId(ref_val))
            elif isinstance(ref_val, ObjectId):
                lookup_candidates.append(ref_str)

            matching_targets = await db[target_col].find(
                {"tenant_id": doc_tenant, "_id": {"$in": lookup_candidates}},
                projection={"_id": 1},
            ).to_list(length=3)

            if len(matching_targets) > 1:
                report["operator_review_required"]["ambiguous_collisions"].append({
                    "relationship": key,
                    "tenant_id": doc_tenant,
                    "source_id": str(doc["_id"]),
                    "reference": ref_str,
                })
                continue

            if not matching_targets:
                report["operator_review_required"]["orphan_references"].append({
                    "relationship": key,
                    "tenant_id": doc_tenant,
                    "source_id": str(doc["_id"]),
                    "reference": ref_str,
                })
                continue

            target_canonical_id = matching_targets[0]["_id"]
            if type(ref_val) is not type(target_canonical_id) or ref_val != target_canonical_id:
                candidates_to_update.append((
                    doc["_id"],
                    doc_tenant,
                    ref_field,
                    target_canonical_id,
                ))

        report["references_normalized"][key] = len(candidates_to_update)
        if apply:
            for doc_id, doc_tenant, field, new_val in candidates_to_update:
                await db[source_col].update_one(
                    {"_id": doc_id, "tenant_id": doc_tenant},
                    {"$set": {field: new_val}},
                )

    # ---------------------------------------------------------
    # Stage 3: Slot ownership and expired hold reconciliation
    # ---------------------------------------------------------
    now = datetime.now(UTC).replace(tzinfo=None)
    expired_holds_cursor = db["slots"].find({
        **scope,
        "status": "held",
        "hold_expiry": {"$lt": now},
    })
    expired_holds = await expired_holds_cursor.to_list(length=batch_size)
    report["expired_holds_released"] = len(expired_holds)
    if apply and expired_holds:
        await db["slots"].update_many(
            {**scope, "status": "held", "hold_expiry": {"$lt": now}},
            {
                "$set": {"status": "open"},
                "$unset": {"hold_owner": "", "hold_expiry": ""},
            },
        )

    booked_slots_cursor = db["slots"].find(
        {**scope, "status": "booked"},
        projection={"_id": 1, "tenant_id": 1, "booking_id": 1},
    )
    async for slot in booked_slots_cursor:
        slot_tenant = slot.get("tenant_id")
        booking_id = slot.get("booking_id")
        if not booking_id:
            matching_booking = await db["bookings"].find_one(
                {"tenant_id": slot_tenant, "slot_id": {"$in": [slot["_id"], str(slot["_id"])]}},
                projection={"_id": 1},
            )
            if matching_booking:
                report["slot_ownership_reconciled"] += 1
                if apply:
                    await db["slots"].update_one(
                        {"_id": slot["_id"], "tenant_id": slot_tenant},
                        {"$set": {"booking_id": matching_booking["_id"]}},
                    )
            else:
                report["operator_review_required"]["unowned_booked_slots"] += 1
        else:
            booking_str = str(booking_id)
            cands: list[Any] = [booking_id]
            if isinstance(booking_id, str) and ObjectId.is_valid(booking_id):
                cands.append(ObjectId(booking_id))
            elif isinstance(booking_id, ObjectId):
                cands.append(booking_str)

            actual_booking = await db["bookings"].find_one(
                {"tenant_id": slot_tenant, "_id": {"$in": cands}},
                projection={"_id": 1},
            )
            if actual_booking and type(booking_id) is not type(actual_booking["_id"]):
                report["slot_ownership_reconciled"] += 1
                if apply:
                    await db["slots"].update_one(
                        {"_id": slot["_id"], "tenant_id": slot_tenant},
                        {"$set": {"booking_id": actual_booking["_id"]}},
                    )

    # ---------------------------------------------------------
    # Stage 4: Timestamp normalization (unambiguous ISO strings only)
    # ---------------------------------------------------------
    for col_name, fields in TIMESTAMP_FIELDS.items():
        for field in fields:
            key = f"{col_name}.{field}"
            cursor = db[col_name].find(
                {**scope, field: {"$type": "string"}},
                projection={"_id": 1, "tenant_id": 1, field: 1},
            )
            to_update: list[tuple[Any, str, datetime]] = []
            async for doc in cursor:
                doc_tenant = doc.get("tenant_id")
                raw_str = doc.get(field)
                parsed_dt = _parse_iso_timestamp(raw_str)
                if parsed_dt and doc_tenant:
                    to_update.append((doc["_id"], doc_tenant, parsed_dt))

            if to_update:
                report["timestamps_normalized"][key] = len(to_update)
                if apply:
                    for doc_id, doc_tenant, dt in to_update:
                        await db[col_name].update_one(
                            {"_id": doc_id, "tenant_id": doc_tenant},
                            {"$set": {field: dt}},
                        )

    # ---------------------------------------------------------
    # Stage 5: Stranded / queued messages classification
    # ---------------------------------------------------------
    stranded = await db["messages"].count_documents({
        **scope,
        "$or": [{"status": "queued"}, {"type": "placeholder"}],
    })
    report["operator_review_required"]["stranded_messages"] = stranded

    # Convert defaultdicts to regular dicts for clean JSON serialization
    report["references_normalized"] = dict(sorted(report["references_normalized"].items()))
    report["timestamps_normalized"] = dict(sorted(report["timestamps_normalized"].items()))
    report["completed_at"] = datetime.now(UTC).isoformat()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", help="Scope migration to a single tenant ID")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--confirm", help="Must be 'MIGRATE' when using --apply")
    args = parser.parse_args()

    if args.apply and args.confirm != "MIGRATE":
        parser.error("--apply requires explicit confirmation --confirm MIGRATE")

    should_apply = args.apply and args.confirm == "MIGRATE"
    result = asyncio.run(
        run_migration(
            tenant_id=args.tenant,
            apply=should_apply,
            batch_size=args.batch_size,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
