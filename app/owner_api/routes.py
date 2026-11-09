"""Owner dashboard REST (TRD §5.2). All routes JWT-authed and tenant-scoped.

Endpoints (stubs — Week 5 task 5.3):
  GET  /conversations           GET  /conversations/{id}/messages
  POST /conversations/{id}/takeover   POST /conversations/{id}/return
  GET  /bookings   POST /bookings   PATCH /bookings/{id}
  GET  /escalations   GET /deliveries   GET /processing
  GET/PUT /kb      GET/PUT /settings
  GET  /metrics/summary          GET  /audit/export
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.channels.whatsapp import send_freeform
from app.config import settings
from app.kb.embedding import embed_text
from app.models.base import mongo_id_candidates, serialize_mongo
from app.models.collections import (
    AuditLog,
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    KbEntries,
    Messages,
    OutboundIntents,
    Tenants,
)
from app.owner_api.auth import require_owner_tenant, require_tenant

router = APIRouter(tags=["owner"])


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        Conversations(tenant_id)
        .find({})
        .sort([("last_msg_at", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.get("/conversations/{id}")
async def get_conversation(
    id: str, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    try:
        conv_id = await Conversations(tenant_id).resolve_id(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if conv_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation = await Conversations(tenant_id).find_one({"_id": conv_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize_mongo(conversation)


@router.get("/conversations/{id}/messages")
async def list_messages(
    id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        Messages(tenant_id)
        .find({"conversation_id": {"$in": mongo_id_candidates(id)}})
        .sort([("ts", 1), ("_id", 1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.post("/conversations/{id}/takeover")
async def takeover_conversation(
    id: str, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    try:
        conv_id = await Conversations(tenant_id).resolve_id(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if conv_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await Conversations(tenant_id).update_one(
        {"_id": conv_id}, {"$set": {"state": "human"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "state": "human"}


class ReturnPayload(BaseModel):
    summary: str


class StaffReplyPayload(BaseModel):
    text: str
    request_id: str


@router.post("/conversations/{id}/reply")
async def reply_to_conversation(
    id: str,
    payload: StaffReplyPayload,
    tenant_id: str = Depends(require_tenant),
) -> dict[str, Any]:
    text = payload.text.strip()
    if not text or not payload.request_id.strip():
        raise HTTPException(status_code=422, detail="Reply text and request ID are required")
    try:
        conv_id = await Conversations(tenant_id).resolve_id(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if conv_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation = await Conversations(tenant_id).find_one({"_id": conv_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.get("state") != "human":
        raise HTTPException(status_code=409, detail="Take over the conversation before replying")
    contact_id = str(conversation.get("contact_id", ""))
    try:
        contact_id_resolved = await Contacts(tenant_id).resolve_id(contact_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    contact = (
        await Contacts(tenant_id).find_one({"_id": contact_id_resolved})
        if contact_id_resolved is not None
        else None
    )
    if not contact or not (contact.get("wa_id") or contact.get("phone")):
        raise HTTPException(status_code=409, detail="Conversation has no reachable contact")
    wa_id = str(contact.get("wa_id") or contact.get("phone"))
    result = await send_freeform(
        tenant_id,
        wa_id,
        text,
        operation_key=f"staff-reply:{payload.request_id.strip()}",
    )
    request_id = payload.request_id.strip()
    await Messages(tenant_id).update_one(
        {"staff_request_id": request_id},
        {
            "$setOnInsert": {
                "conversation_id": str(conv_id),
                "direction": "outbound",
                "type": "text",
                "text": text,
                "actor": "staff",
                "staff_request_id": request_id,
                "provider_message_id": result.get("messages", [{}])[0].get("id"),
                "ts": datetime.now(UTC).replace(tzinfo=None),
            }
        },
        upsert=True,
    )
    return {"status": "sent", "deduplicated": bool(result.get("deduplicated"))}


@router.post("/conversations/{id}/return")
async def return_conversation(
    id: str, payload: ReturnPayload, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(status_code=422, detail="Resolution summary is required")
    try:
        conv_id = await Conversations(tenant_id).resolve_id(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if conv_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await Conversations(tenant_id).update_one(
        {"_id": conv_id}, {"$set": {"state": "bot"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await Messages(tenant_id).insert_one({
        "conversation_id": str(conv_id),
        "direction": "system",
        "type": "resolution_summary",
        "text": summary,
        "ts": datetime.now(UTC).replace(tzinfo=None)
    })
    await Escalations(tenant_id).update_one(
        {"conversation_id": {"$in": mongo_id_candidates(str(conv_id))}, "status": "open"},
        {
            "$set": {
                "status": "resolved",
                "resolution_summary": summary,
                "resolved_at": datetime.now(UTC).replace(tzinfo=None),
            }
        },
    )
    return {"status": "success", "state": "bot"}


@router.get("/bookings")
async def list_bookings(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        Bookings(tenant_id)
        .find({})
        .sort([("ts", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.get("/bookings/{id}")
async def get_booking(
    id: str, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    try:
        booking_id = await Bookings(tenant_id).resolve_id(id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if booking_id is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking = await Bookings(tenant_id).find_one({"_id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return serialize_mongo(booking)


class BookingCreate(BaseModel):
    slot_id: str
    contact_id: str
    service: str
    request_id: str


@router.post("/bookings")
async def create_booking_api(
    payload: BookingCreate, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    from app.booking.engine import create_booking
    booking = await create_booking(
        tenant_id, payload.slot_id, payload.contact_id, payload.service, payload.request_id
    )
    if not booking:
        raise HTTPException(status_code=400, detail="Booking confirmation failed")
    return booking


class BookingUpdate(BaseModel):
    status: str
    new_slot_id: str | None = None
    request_id: str | None = None


@router.patch("/bookings/{id}")
async def update_booking_api(
    id: str, payload: BookingUpdate, tenant_id: str = Depends(require_tenant)
) -> dict[str, Any]:
    from app.booking.engine import cancel_booking, move_booking

    try:
        if payload.status == "cancelled":
            booking = await cancel_booking(tenant_id, id)
            if not booking:
                raise HTTPException(status_code=404, detail="Booking not found")
            return {"status": "success", "booking_id": str(booking.get("_id", id))}
        if payload.status == "rescheduled":
            if not payload.new_slot_id or not payload.request_id:
                raise HTTPException(
                    status_code=422,
                    detail="new_slot_id and request_id are required",
                )
            result = await move_booking(
                tenant_id, id, payload.new_slot_id, payload.request_id
            )
            if not result:
                raise HTTPException(status_code=409, detail="Booking or slot is unavailable")
            return result
        raise HTTPException(status_code=422, detail="Unsupported booking transition")
    except ValueError as e:
        if "ambiguous" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e)) from e
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/escalations")
async def list_escalations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        Escalations(tenant_id)
        .find({})
        .sort([("ts", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.get("/deliveries")
async def list_delivery_exceptions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        OutboundIntents(tenant_id)
        .find(
            {"state": {"$in": ["sending", "unknown", "failed"]}},
            {
                "state": 1,
                "kind": 1,
                "attempted_at": 1,
                "reconciled_at": 1,
                "last_error": 1,
            },
        )
        .sort([("attempted_at", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.get("/processing")
async def list_processing_failures(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        Messages(tenant_id)
        .find(
            {"status": "failed"},
            {
                "status": 1,
                "attempts": 1,
                "accepted_at": 1,
                "failed_at": 1,
                "fail_reason": 1,
            },
        )
        .sort([("failed_at", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


@router.get("/kb")
async def list_kb(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        KbEntries(tenant_id)
        .find(
            {},
            {
                "question": 1,
                "answer": 1,
                "kind": 1,
                "key": 1,
                "version": 1,
                "ts": 1,
            },
        )
        .sort([("question", 1), ("_id", 1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)


class KbUpsert(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=5000)
    kind: Literal["field", "faq"] = "faq"


@router.put("/kb")
async def upsert_kb(payload: KbUpsert, tenant_id: str = Depends(require_tenant)) -> dict[str, Any]:
    question = payload.question.strip()
    answer = payload.answer.strip()
    if not question or not answer:
        raise HTTPException(status_code=422, detail="Question and answer are required")
    try:
        embedding = await embed_text(
            f"{question}\n{answer}", input_type="search_document"
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Knowledge embedding is unavailable; entry was not saved",
        ) from error
    await KbEntries(tenant_id).update_one(
        {"question": question},
        {
            "$set": {
                "answer": answer,
                "kind": payload.kind,
                "embedding": embedding,
                "embedding_model": settings.llm_model_embedding or "mock",
                "embedding_dimensions": len(embedding),
                "ts": datetime.now(UTC).replace(tzinfo=None),
            },
            "$inc": {"version": 1},
        },
        upsert=True
    )
    return {"status": "success"}


@router.get("/settings")
async def get_settings_api(tenant_id: str = Depends(require_tenant)) -> dict[str, Any]:
    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return serialize_mongo(tenant)


class SettingsUpdate(BaseModel):
    name: str
    landmark_line: str
    location_pin: str


@router.put("/settings")
async def update_settings_api(
    payload: SettingsUpdate, tenant_id: str = Depends(require_owner_tenant)
) -> dict[str, Any]:
    await Tenants.update_settings(tenant_id, payload.model_dump())
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
async def export_audit(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(require_owner_tenant),
) -> list[dict[str, Any]]:
    cursor = (
        AuditLog(tenant_id)
        .find({})
        .sort([("ts", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )
    results: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return serialize_mongo(results)
