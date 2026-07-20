"""Owner dashboard REST (TRD §5.2). All routes JWT-authed and tenant-scoped.

Endpoints (stubs — Week 5 task 5.3):
  GET  /conversations           GET  /conversations/{id}/messages
  POST /conversations/{id}/takeover   POST /conversations/{id}/return
  GET  /bookings   POST /bookings   PATCH /bookings/{id}
  GET  /escalations
  GET/PUT /kb      GET/PUT /settings
  GET  /metrics/summary          GET  /audit/export
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.base import get_db
from app.models.collections import (
    AuditLog,
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    KbEntries,
    Messages,
    Tenants,
)
from app.owner_api.auth import require_tenant

router = APIRouter(tags=["owner"])


@router.get("/conversations")
async def list_conversations(tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = Conversations(tenant_id).find({})
    results: list[dict[str, Any]] = await cursor.to_list(length=100)
    return results


@router.get("/conversations/{id}/messages")
async def list_messages(id: str, tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = Messages(tenant_id).find({"conversation_id": id})
    results: list[dict[str, Any]] = await cursor.to_list(length=200)
    return results


@router.post("/conversations/{id}/takeover")
async def takeover_conversation(
    id: str, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    await Conversations(tenant_id).update_one({"_id": id}, {"$set": {"state": "human"}})
    return {"status": "success", "state": "human"}


class ReturnPayload(BaseModel):
    summary: str


@router.post("/conversations/{id}/return")
async def return_conversation(
    id: str, payload: ReturnPayload, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    await Conversations(tenant_id).update_one({"_id": id}, {"$set": {"state": "bot"}})
    await Messages(tenant_id).insert_one({
        "conversation_id": id,
        "direction": "system",
        "type": "resolution_summary",
        "text": payload.summary,
        "ts": datetime.now(UTC).replace(tzinfo=None)
    })
    return {"status": "success", "state": "bot"}


@router.get("/bookings")
async def list_bookings(tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = Bookings(tenant_id).find({})
    results: list[dict[str, Any]] = await cursor.to_list(length=100)
    return results


class BookingCreate(BaseModel):
    slot_id: str
    contact_id: str
    service: str


@router.post("/bookings")
async def create_booking_api(
    payload: BookingCreate, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    from app.booking.engine import confirm_booking, hold_slot
    held = await hold_slot(tenant_id, payload.slot_id)
    if not held:
        raise HTTPException(status_code=400, detail="Slot is not available")
    booking = await confirm_booking(tenant_id, payload.slot_id, payload.contact_id, payload.service)
    if not booking:
        raise HTTPException(status_code=400, detail="Booking confirmation failed")
    return booking


class BookingUpdate(BaseModel):
    status: str


@router.patch("/bookings/{id}")
async def update_booking_api(
    id: str, payload: BookingUpdate, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    await Bookings(tenant_id).update_one({"_id": id}, {"$set": {"status": payload.status}})
    return {"status": "success", "booking_id": id}


@router.get("/escalations")
async def list_escalations(tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = Escalations(tenant_id).find({})
    results: list[dict[str, Any]] = await cursor.to_list(length=100)
    return results


@router.get("/kb")
async def list_kb(tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = KbEntries(tenant_id).find({})
    results: list[dict[str, Any]] = await cursor.to_list(length=100)
    return results


class KbUpsert(BaseModel):
    question: str
    answer: str
    kind: str = "faq"


@router.put("/kb")
async def upsert_kb(payload: KbUpsert, tenant_id: str = Depends(require_tenant)) -> dict[str, Any]:
    await KbEntries(tenant_id).update_one(
        {"question": payload.question},
        {
            "$set": {
                "answer": payload.answer,
                "kind": payload.kind,
                "ts": datetime.now(UTC).replace(tzinfo=None)
            }
        },
        upsert=True
    )
    return {"status": "success"}


@router.get("/settings")
async def get_settings_api(tenant_id: str = Depends(require_tenant)) -> dict[str, Any]:
    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


class SettingsUpdate(BaseModel):
    name: str
    landmark_line: str
    location_pin: str


@router.put("/settings")
async def update_settings_api(
    payload: SettingsUpdate, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    await get_db()["tenants"].update_one(
        {"_id": tenant_id},
        {
            "$set": {
                "name": payload.name,
                "landmark_line": payload.landmark_line,
                "location_pin": payload.location_pin
            }
        }
    )
    return {"status": "success"}


@router.get("/metrics/summary")
async def metrics_summary(tenant_id: str = Depends(require_tenant)) -> dict[str, Any]:
    bookings_count = await Bookings(tenant_id).count_documents({})
    contacts_cursor = Contacts(tenant_id).find({"profile.csat_avg": {"$exists": True}})
    contacts_list = await contacts_cursor.to_list(length=1000)
    csat_total = sum(c.get("profile", {}).get("csat_avg", 0.0) for c in contacts_list)
    csat_avg = csat_total / len(contacts_list) if contacts_list else 0.0
    return {
        "total_bookings": bookings_count,
        "csat_average": csat_avg
    }


@router.get("/audit/export")
async def export_audit(tenant_id: str = Depends(require_tenant)) -> list[dict[str, Any]]:
    cursor = AuditLog(tenant_id).find({})
    results: list[dict[str, Any]] = await cursor.to_list(length=1000)
    return results
