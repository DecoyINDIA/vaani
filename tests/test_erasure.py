from __future__ import annotations

import json

import pytest
from app.channels.whatsapp import SuppressedRecipientError, send_template
from app.models.base import get_db
from app.privacy import is_suppressed
from ops.dpdp_delete import erase_patient


async def test_erasure_dry_run_apply_idempotency_and_tenant_isolation() -> None:
    db = get_db()
    tenant_id = "t_erasure"
    other_tenant = "t_erasure_other"
    phone = "944444444444"
    contact_id = "erase-contact"
    conversation_id = "erase-conversation"
    booking_id = "erase-booking"

    await db["contacts"].insert_many(
        [
            {
                "_id": contact_id,
                "tenant_id": tenant_id,
                "wa_id": phone,
                "phone": phone,
                "name": "Synthetic Patient",
            },
            {
                "_id": "other-contact",
                "tenant_id": other_tenant,
                "wa_id": phone,
                "phone": phone,
                "name": "Other Tenant Patient",
            },
        ]
    )
    await db["conversations"].insert_one(
        {"_id": conversation_id, "tenant_id": tenant_id, "contact_id": contact_id}
    )
    await db["messages"].insert_many(
        [
            {
                "_id": "erase-message",
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "text": f"Call me at {phone}",
            },
            {
                "_id": "erase-queued",
                "tenant_id": tenant_id,
                "status": "queued",
                "payload": {"from": phone},
            },
        ]
    )
    await db["bookings"].insert_one(
        {
            "_id": booking_id,
            "tenant_id": tenant_id,
            "contact_id": contact_id,
            "status": "confirmed",
        }
    )
    await db["payments"].insert_one(
        {
            "_id": "retained-payment",
            "tenant_id": tenant_id,
            "contact_id": contact_id,
            "booking_id": booking_id,
            "note": "Synthetic Patient",
        }
    )
    await db["audit_log"].insert_one(
        {
            "_id": "retained-audit",
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "payload": {"phone": phone, "name": "Synthetic Patient"},
        }
    )
    await db["outbound_intents"].insert_one(
        {
            "_id": "pending-send",
            "tenant_id": tenant_id,
            "operation_key": "pending-erasure-send",
            "to": phone,
            "state": "pending",
        }
    )

    dry_run = await erase_patient(
        tenant_id, contact_id, request_id="erase-request", apply=False
    )
    assert dry_run["status"] == "dry_run"
    assert phone not in json.dumps(dry_run)
    assert await db["contacts"].find_one({"_id": contact_id}) is not None

    applied = await erase_patient(
        tenant_id,
        contact_id,
        request_id="erase-request",
        authorized_by="synthetic-operator",
        apply=True,
    )
    assert applied["status"] == "completed"
    assert await db["contacts"].find_one({"_id": contact_id}) is None
    assert await db["contacts"].find_one({"_id": "other-contact"}) is not None
    assert await db["messages"].count_documents({"tenant_id": tenant_id}) == 0
    assert await db["bookings"].count_documents({"tenant_id": tenant_id}) == 0

    payment = await db["payments"].find_one({"_id": "retained-payment"})
    audit = await db["audit_log"].find_one({"_id": "retained-audit"})
    outbound = await db["outbound_intents"].find_one({"_id": "pending-send"})
    assert phone not in json.dumps(payment, default=str)
    assert contact_id not in json.dumps(payment, default=str)
    assert booking_id not in json.dumps(payment, default=str)
    assert phone not in json.dumps(audit, default=str)
    assert "conversation_id" not in audit
    assert outbound["state"] == "suppressed"
    assert outbound["to"] == "[erased]"
    assert await is_suppressed(tenant_id, phone) is True

    with pytest.raises(SuppressedRecipientError):
        await send_template(
            tenant_id,
            phone,
            "booking_confirm",
            {"name": "Patient"},
            operation_key="post-erasure-send",
        )

    repeated = await erase_patient(
        tenant_id,
        contact_id,
        request_id="erase-request",
        authorized_by="synthetic-operator",
        apply=True,
    )
    assert repeated["status"] == "already_completed"
