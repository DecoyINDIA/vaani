from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.booking.timefmt import tenant_timezone
from app.models.base import mongo_id_candidates
from app.models.collections import (
    Contacts,
    Escalations,
    Messages,
    Practitioners,
    Slots,
    Tenants,
)


def _to_tenant_iso(dt: datetime | None, tz: ZoneInfo) -> str | None:
    if not dt or not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=UTC).astimezone(tz)
    else:
        aware = dt.astimezone(tz)
    return aware.isoformat()


async def enrich_conversations(
    tenant_id: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rows:
        return []

    tenant = await Tenants.find_by_id(tenant_id)
    tz = tenant_timezone(tenant)

    # 1. Batch contact lookup
    contact_cands: list[Any] = []
    for r in rows:
        cid = r.get("contact_id")
        if cid:
            contact_cands.extend(mongo_id_candidates(str(cid)))

    contacts_map: dict[str, dict[str, Any]] = {}
    if contact_cands:
        cursor = Contacts(tenant_id).find({"_id": {"$in": contact_cands}})
        async for c in cursor:
            cid_str = str(c["_id"])
            phone = str(c.get("wa_id") or c.get("phone") or "")
            summary = {
                "id": cid_str,
                "name": str(c.get("name") or ""),
                "phone": phone,
            }
            contacts_map[cid_str] = summary

    # 2. Batch escalations lookup
    conv_ids: list[str] = [str(r["_id"]) for r in rows if "_id" in r]
    escalation_cands: list[Any] = []
    for cid in conv_ids:
        escalation_cands.extend(mongo_id_candidates(cid))

    open_escalation_conv_ids: set[str] = set()
    if escalation_cands:
        all_conv_ids = conv_ids + [str(c) for c in escalation_cands]
        cursor = Escalations(tenant_id).find(
            {"conversation_id": {"$in": all_conv_ids}, "status": "open"}
        )
        async for esc in cursor:
            open_escalation_conv_ids.add(str(esc.get("conversation_id")))

    # 3. Enrich each conversation row
    for r in rows:
        cid = str(r.get("contact_id", ""))
        r["contact"] = contacts_map.get(cid)

        # Last message lookup (one find_one per conversation, sorted ts desc)
        conv_id_cands = mongo_id_candidates(str(r["_id"]))
        last_msg = await Messages(tenant_id).find_one(
            {"conversation_id": {"$in": [str(r["_id"])] + [str(c) for c in conv_id_cands]}},
            sort=[("ts", -1)],
        )

        if last_msg and last_msg.get("text"):
            text = str(last_msg["text"])
            r["last_message_preview"] = text[:80]
        else:
            r["last_message_preview"] = ""

        # last_msg_at
        ts = r.get("last_msg_at")
        if ts is None and last_msg:
            ts = last_msg.get("ts")
        if isinstance(ts, datetime):
            r["last_msg_at"] = _to_tenant_iso(ts, tz)
        elif isinstance(ts, str):
            try:
                dt_parsed = datetime.fromisoformat(ts)
                r["last_msg_at"] = _to_tenant_iso(dt_parsed, tz)
            except Exception:
                r["last_msg_at"] = ts
        else:
            r["last_msg_at"] = None

        r["open_escalation"] = (
            str(r["_id"]) in open_escalation_conv_ids
            or any(str(c) in open_escalation_conv_ids for c in conv_id_cands)
        )

    return rows


async def enrich_bookings(
    tenant_id: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rows:
        return []

    tenant = await Tenants.find_by_id(tenant_id)
    tz = tenant_timezone(tenant)

    # 1. Batch contact lookup
    contact_cands: list[Any] = []
    for r in rows:
        cid = r.get("contact_id")
        if cid:
            contact_cands.extend(mongo_id_candidates(str(cid)))

    contacts_map: dict[str, dict[str, Any]] = {}
    if contact_cands:
        cursor = Contacts(tenant_id).find({"_id": {"$in": contact_cands}})
        async for c in cursor:
            cid_str = str(c["_id"])
            phone = str(c.get("wa_id") or c.get("phone") or "")
            summary = {
                "id": cid_str,
                "name": str(c.get("name") or ""),
                "phone": phone,
            }
            contacts_map[cid_str] = summary

    # 2. Batch slot lookup
    slot_cands: list[Any] = []
    for r in rows:
        sid = r.get("slot_id")
        if sid:
            slot_cands.extend(mongo_id_candidates(str(sid)))

    slots_map: dict[str, dict[str, Any]] = {}
    if slot_cands:
        cursor = Slots(tenant_id).find({"_id": {"$in": slot_cands}})
        async for s in cursor:
            slots_map[str(s["_id"])] = s

    # 3. Batch practitioner lookup
    practitioner_ids = list(
        {
            str(s.get("practitioner_id"))
            for s in slots_map.values()
            if s.get("practitioner_id")
        }
    )
    practitioners_map: dict[str, dict[str, Any]] = {}
    if practitioner_ids:
        cursor = Practitioners(tenant_id).find({"_id": {"$in": practitioner_ids}})
        async for p in cursor:
            pid_str = str(p["_id"])
            practitioners_map[pid_str] = {
                "id": pid_str,
                "name": str(p.get("name") or ""),
            }

    # 4. Enrich each booking row
    for r in rows:
        cid = str(r.get("contact_id", ""))
        r["contact"] = contacts_map.get(cid)

        sid = str(r.get("slot_id", ""))
        slot = slots_map.get(sid)
        if slot:
            r["start"] = _to_tenant_iso(slot.get("start"), tz)
            r["end"] = _to_tenant_iso(slot.get("end"), tz)
            pid = str(slot.get("practitioner_id", ""))
            r["practitioner"] = practitioners_map.get(pid)
        else:
            r["start"] = None
            r["end"] = None
            r["practitioner"] = None

    return rows
