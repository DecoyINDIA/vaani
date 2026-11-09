"""External erasure ledger operation: export, restore replay, and suppression verification."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.base import get_db
from app.privacy import identifier_hash, is_suppressed

from ops.dpdp_delete import erase_patient


async def export_ledger(
    output_path: Path, *, tenant_id: str | None = None
) -> dict[str, Any]:
    """Export completed erasure requests and hashed suppression markers with zero raw PII."""
    db = get_db()
    query: dict[str, Any] = {"status": "completed"}
    suppression_query: dict[str, Any] = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
        suppression_query["tenant_id"] = tenant_id

    requests = await db["erasure_requests"].find(query).to_list(length=None)
    suppressions = await db["erasure_suppression"].find(suppression_query).to_list(length=None)

    exported_requests = []
    for req in requests:
        completed_at = req.get("completed_at")
        exported_requests.append({
            "request_id": str(req.get("request_id")),
            "tenant_id": str(req.get("tenant_id")),
            "status": req.get("status"),
            "contact_hash": req.get("contact_hash"),
            "authorized_by": req.get("authorized_by"),
            "counts": req.get("counts", {}),
            "provider_case_ids": req.get("provider_case_ids", {}),
            "provider_deletion_obligations": req.get("provider_deletion_obligations", []),
            "completed_at": (
                completed_at.isoformat()
                if isinstance(completed_at, datetime)
                else str(completed_at or "")
            ),
        })

    exported_suppressions = []
    for sup in suppressions:
        created_at = sup.get("created_at")
        exported_suppressions.append({
            "tenant_id": str(sup.get("tenant_id")),
            "contact_hash": sup.get("contact_hash"),
            "identifier_hashes": sorted(sup.get("identifier_hashes", [])),
            "request_id": str(sup.get("request_id")),
            "created_at": (
                created_at.isoformat()
                if isinstance(created_at, datetime)
                else str(created_at or "")
            ),
        })

    payload = {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "total_requests": len(exported_requests),
        "total_suppression_markers": len(exported_suppressions),
        "requests": exported_requests,
        "suppression_markers": exported_suppressions,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


async def replay_ledger(
    ledger_path: Path,
    *,
    tenant_id: str | None = None,
    authorized_by: str = "restore_replay_operator",
) -> dict[str, Any]:
    """Replay external erasure ledger on a restored database before traffic is reopened."""
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    db = get_db()
    now = datetime.now(UTC).replace(tzinfo=None)

    suppression_markers = data.get("suppression_markers", [])
    erasure_requests = data.get("requests", [])

    imported_suppressions = 0
    replayed_erasures = 0
    already_erased = 0

    # 1. Immediately import all suppression markers into erasure_suppression
    for marker in suppression_markers:
        marker_tenant = marker["tenant_id"]
        if tenant_id and marker_tenant != tenant_id:
            continue
        created_at_raw = marker.get("created_at")
        created_at = now
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(created_at_raw).replace(tzinfo=None)
            except ValueError:
                pass
        await db["erasure_suppression"].update_one(
            {"tenant_id": marker_tenant, "contact_hash": marker["contact_hash"]},
            {
                "$set": {
                    "identifier_hashes": marker["identifier_hashes"],
                    "request_id": marker["request_id"],
                    "created_at": created_at,
                    "reapplied_at": now,
                }
            },
            upsert=True,
        )
        imported_suppressions += 1

    # 2. For each request, check if the restored DB contains older restored data for that patient
    for req in erasure_requests:
        req_tenant = req["tenant_id"]
        if tenant_id and req_tenant != tenant_id:
            continue

        contact_hash = req.get("contact_hash")
        hashes: set[str] = set()
        for marker in suppression_markers:
            if marker["tenant_id"] == req_tenant and marker["contact_hash"] == contact_hash:
                hashes.update(marker.get("identifier_hashes", []))

        # Scan contacts for this tenant
        contacts = await db["contacts"].find({"tenant_id": req_tenant}).to_list(length=None)
        found_contact_id: str | None = None
        for c in contacts:
            c_id = str(c["_id"])
            phone = str(c.get("phone", ""))
            wa_id = str(c.get("wa_id", ""))
            if (
                identifier_hash(req_tenant, c_id) in hashes
                or identifier_hash(req_tenant, phone) in hashes
                or identifier_hash(req_tenant, wa_id) in hashes
            ):
                found_contact_id = c_id
                break

        if found_contact_id:
            # Reapply erasure on restored patient
            await erase_patient(
                req_tenant,
                found_contact_id,
                request_id=req["request_id"],
                authorized_by=authorized_by,
                apply=True,
                provider_case_ids=req.get("provider_case_ids"),
            )
            replayed_erasures += 1
        else:
            already_erased += 1
            completed_at_raw = req.get("completed_at")
            completed_at = now
            if completed_at_raw:
                try:
                    completed_at = datetime.fromisoformat(completed_at_raw).replace(tzinfo=None)
                except ValueError:
                    pass
            await db["erasure_requests"].update_one(
                {"tenant_id": req_tenant, "request_id": req["request_id"]},
                {
                    "$set": {
                        "status": "completed",
                        "contact_hash": contact_hash,
                        "counts": req.get("counts", {}),
                        "provider_case_ids": req.get("provider_case_ids", {}),
                        "provider_deletion_obligations": req.get(
                            "provider_deletion_obligations", []
                        ),
                        "completed_at": completed_at,
                        "replayed_at": now,
                    }
                },
                upsert=True,
            )

    return {
        "status": "success",
        "imported_suppression_markers": imported_suppressions,
        "replayed_erasures": replayed_erasures,
        "already_clean_cases": already_erased,
        "replayed_at": now.isoformat(),
    }


async def verify_erasure_state(tenant_id: str, identifier: str) -> dict[str, Any]:
    """Verify that an identifier is suppressed and no un-pseudonymized contact/booking exists."""
    db = get_db()
    suppressed = await is_suppressed(tenant_id, identifier)
    contact_exists = (
        await db["contacts"].find_one({
            "tenant_id": tenant_id,
            "$or": [{"phone": identifier}, {"wa_id": identifier}],
        })
        is not None
    )
    return {
        "tenant_id": tenant_id,
        "suppressed": suppressed,
        "contact_clean": not contact_exists,
        "verified": suppressed and not contact_exists,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="External erasure ledger operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_p = subparsers.add_parser("export", help="Export external ledger")
    export_p.add_argument("--output", type=Path, required=True)
    export_p.add_argument("--tenant")

    replay_p = subparsers.add_parser("replay", help="Replay ledger on restored database")
    replay_p.add_argument("--ledger", type=Path, required=True)
    replay_p.add_argument("--tenant")
    replay_p.add_argument("--authorized-by", default="restore_replay_operator")

    verify_p = subparsers.add_parser("verify", help="Verify erasure suppression")
    verify_p.add_argument("--tenant", required=True)
    verify_p.add_argument("--identifier", required=True)

    args = parser.parse_args()
    if args.command == "export":
        res = await export_ledger(args.output, tenant_id=args.tenant)
    elif args.command == "replay":
        res = await replay_ledger(
            args.ledger, tenant_id=args.tenant, authorized_by=args.authorized_by
        )
    else:
        res = await verify_erasure_state(args.tenant, args.identifier)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
