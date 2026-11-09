"""Comprehensive retention, erasure, external ledger, and restore acceptance suite (WP10 / R15 / R08)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.channels.whatsapp import SuppressedRecipientError, send_template
from app.models.base import get_db
from app.privacy import is_suppressed
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ops.dpdp_delete import erase_patient
from ops.erasure_ledger import export_ledger, replay_ledger, verify_erasure_state


@pytest.mark.asyncio
async def test_erasure_lifecycle_slots_unlinking_and_provider_cases() -> None:
    db = get_db()
    tenant_id = "tenant-erasure-clinic"
    contact_id = "patient-alpha"
    phone = "919876543210"
    booking_id = "booking-alpha"
    slot_id = "slot-alpha"

    # Setup contact, slot, booking, messages, waitlist, escalation, voice grant, payment, audit, outbound
    await db["contacts"].insert_one({
        "_id": contact_id,
        "tenant_id": tenant_id,
        "phone": phone,
        "wa_id": phone,
        "name": "Dr. Patient Alpha",
    })
    await db["conversations"].insert_one({
        "_id": "conv-alpha",
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "state": "bot",
    })
    await db["messages"].insert_many([
        {
            "_id": "msg-alpha-1",
            "tenant_id": tenant_id,
            "conversation_id": "conv-alpha",
            "text": f"Appointment request for {phone}",
        },
        {
            "_id": "msg-alpha-2",
            "tenant_id": tenant_id,
            "status": "queued",
            "payload": {"from": phone, "body": "Need consultation"},
        },
    ])
    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "booked",
        "booking_id": booking_id,
    })
    await db["bookings"].insert_one({
        "_id": booking_id,
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "slot_id": slot_id,
        "status": "confirmed",
    })
    await db["waitlist"].insert_one({
        "_id": "waitlist-alpha",
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "service": "General Consultation",
    })
    await db["escalations"].insert_one({
        "_id": "esc-alpha",
        "tenant_id": tenant_id,
        "conversation_id": "conv-alpha",
        "status": "open",
    })
    await db["voice_grants"].insert_one({
        "_id": "grant-alpha",
        "tenant_id": tenant_id,
        "call_sid": "call-alpha",
        "caller_phone": phone,
    })
    await db["payments"].insert_one({
        "_id": "pay-alpha",
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "booking_id": booking_id,
        "amount_paise": 50000,
        "status": "paid",
        "notes": f"Payment for Dr. Patient Alpha phone {phone}",
    })
    await db["audit_log"].insert_one({
        "_id": "audit-alpha",
        "tenant_id": tenant_id,
        "conversation_id": "conv-alpha",
        "event_type": "booking_confirmed",
        "payload": {"patient_name": "Dr. Patient Alpha", "phone": phone},
    })
    await db["outbound_intents"].insert_one({
        "_id": "outbound-alpha",
        "tenant_id": tenant_id,
        "operation_key": "reminder:alpha",
        "to": phone,
        "state": "pending",
    })

    # Dry run
    dry_run = await erase_patient(
        tenant_id,
        contact_id,
        request_id="REQ-DPDP-001",
        apply=False,
    )
    assert dry_run["status"] == "dry_run"
    assert dry_run["counts"]["contacts_delete"] == 1
    assert dry_run["counts"]["bookings_delete"] == 1
    assert dry_run["counts"]["slots_unlinked"] == 1
    assert dry_run["counts"]["voice_grants_delete"] == 1
    assert dry_run["counts"]["payments_pseudonymize"] == 1
    assert dry_run["counts"]["audit_pseudonymize"] == 1
    assert dry_run["counts"]["outbound_suppress"] == 1
    assert phone not in json.dumps(dry_run)

    # Verify dry run did not mutate DB
    assert await db["contacts"].find_one({"_id": contact_id}) is not None
    slot_before = await db["slots"].find_one({"_id": slot_id})
    assert slot_before is not None and slot_before["status"] == "booked"

    # Apply erasure with provider case IDs
    provider_cases = {
        "meta_whatsapp": "WABA-TICKET-8891",
        "exotel": "EXO-DELETE-2341",
        "sarvam_ai": "SARVAM-REQ-1102",
        "razorpay": "RZP-MASK-9921",
    }
    applied = await erase_patient(
        tenant_id,
        contact_id,
        request_id="REQ-DPDP-001",
        authorized_by="compliance_officer_1",
        apply=True,
        provider_case_ids=provider_cases,
    )
    assert applied["status"] == "completed"

    # Verify clinical records erased
    assert await db["contacts"].find_one({"_id": contact_id}) is None
    assert await db["conversations"].find_one({"_id": "conv-alpha"}) is None
    assert await db["messages"].find_one({"_id": "msg-alpha-1"}) is None
    assert await db["messages"].find_one({"_id": "msg-alpha-2"}) is None
    assert await db["bookings"].find_one({"_id": booking_id}) is None
    assert await db["waitlist"].find_one({"_id": "waitlist-alpha"}) is None
    assert await db["escalations"].find_one({"_id": "esc-alpha"}) is None
    assert await db["voice_grants"].find_one({"_id": "grant-alpha"}) is None

    # Verify slot unlinked and opened
    slot_after = await db["slots"].find_one({"_id": slot_id})
    assert slot_after is not None
    assert slot_after["status"] == "open"
    assert "booking_id" not in slot_after

    # Verify payment pseudonymized and preserved for financial audit
    payment = await db["payments"].find_one({"_id": "pay-alpha"})
    assert payment is not None
    assert payment["contact_id"] == "[erased]"
    assert phone not in json.dumps(payment, default=str)
    assert "Dr. Patient Alpha" not in json.dumps(payment, default=str)
    assert payment["amount_paise"] == 50000

    # Verify audit log scrubbed and unlinked
    audit_rec = await db["audit_log"].find_one({"_id": "audit-alpha"})
    assert audit_rec is not None
    assert "conversation_id" not in audit_rec
    assert phone not in json.dumps(audit_rec, default=str)

    # Verify outbound intent suppressed
    outbound = await db["outbound_intents"].find_one({"_id": "outbound-alpha"})
    assert outbound is not None
    assert outbound["state"] == "suppressed"
    assert outbound["to"] == "[erased]"

    # Verify suppression active
    assert await is_suppressed(tenant_id, phone) is True

    # Verify erasure request recorded with provider case IDs
    erasure_req = await db["erasure_requests"].find_one({"request_id": "REQ-DPDP-001"})
    assert erasure_req is not None
    assert erasure_req["status"] == "completed"
    assert erasure_req["provider_case_ids"] == provider_cases

    # Idempotent re-run
    repeated = await erase_patient(
        tenant_id,
        contact_id,
        request_id="REQ-DPDP-001",
        authorized_by="compliance_officer_1",
        apply=True,
    )
    assert repeated["status"] == "already_completed"


@pytest.mark.asyncio
async def test_erased_caller_voice_and_missed_call_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.gateway.exotel.verify_exotel_call",
        AsyncMock(return_value={"Call": {"Sid": "verified-call"}}),
    )
    db = get_db()
    tenant_id = "tenant-voice-erasure"
    erased_phone = "919988776655"
    voice_number = "918000111222"

    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Voice Erasure Clinic",
        "voice_number": voice_number,
        "wa_number": "919999000000",
    })
    # Erase the phone upfront via suppression
    from app.privacy import identifier_hash
    await db["erasure_suppression"].insert_one({
        "tenant_id": tenant_id,
        "contact_hash": identifier_hash(tenant_id, erased_phone),
        "identifier_hashes": [identifier_hash(tenant_id, erased_phone)],
        "request_id": "REQ-VOICE-SUPPRESS",
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    })

    from app.gateway.exotel import router
    test_app = FastAPI()
    test_app.include_router(router, prefix="/webhooks")
    client = TestClient(test_app)

    # 1. Missed call from erased phone
    resp_missed = client.post(
        "/webhooks/exotel/missed_call",
        data={"From": erased_phone, "To": voice_number, "CallSid": "call-suppressed-missed"},
    )
    assert resp_missed.status_code == 200
    assert resp_missed.text == "Suppressed caller"
    # Verify contact was NOT recreated
    assert await db["contacts"].find_one({"tenant_id": tenant_id, "phone": erased_phone}) is None
    assert await db["conversations"].count_documents({"tenant_id": tenant_id}) == 0

    # 2. Inbound call from erased phone
    resp_call = client.post(
        "/webhooks/exotel",
        data={"From": erased_phone, "To": voice_number, "CallSid": "call-suppressed-incoming"},
    )
    assert resp_call.status_code == 200
    assert "This number is not registered on the Vaani platform." in resp_call.text
    assert "<Hangup/>" in resp_call.text
    # Verify no stream grant was issued
    assert await db["voice_grants"].find_one({"tenant_id": tenant_id, "call_sid": "call-suppressed-incoming"}) is None

    # 3. Outbound WhatsApp send to erased phone raises SuppressedRecipientError
    with pytest.raises(SuppressedRecipientError):
        await send_template(
            tenant_id,
            erased_phone,
            "booking_confirm",
            {"name": "Erased Patient"},
            operation_key="outbound-erased-test",
        )


@pytest.mark.asyncio
async def test_external_erasure_ledger_export_and_restore_replay(tmp_path: Path) -> None:
    db = get_db()
    tenant_1 = "clinic-alpha-ledger"
    tenant_2 = "clinic-beta-ledger"
    phone_alpha = "919111111111"
    phone_beta = "919222222222"

    # Setup patient in tenant 1 and patient in tenant 2
    await db["contacts"].insert_many([
        {
            "_id": "contact-alpha",
            "tenant_id": tenant_1,
            "phone": phone_alpha,
            "wa_id": phone_alpha,
            "name": "Patient Alpha",
        },
        {
            "_id": "contact-beta",
            "tenant_id": tenant_2,
            "phone": phone_beta,
            "wa_id": phone_beta,
            "name": "Patient Beta",
        },
    ])
    await db["messages"].insert_many([
        {
            "_id": "msg-alpha",
            "tenant_id": tenant_1,
            "text": f"Alpha text with {phone_alpha}",
        },
        {
            "_id": "msg-beta",
            "tenant_id": tenant_2,
            "text": f"Beta text with {phone_beta}",
        },
    ])

    # Snapshot of the database state before Alpha's erasure
    saved_alpha_contact = await db["contacts"].find_one({"_id": "contact-alpha"})
    saved_alpha_msg = await db["messages"].find_one({"_id": "msg-alpha"})

    # Erase Patient Alpha
    await erase_patient(
        tenant_1,
        "contact-alpha",
        request_id="REQ-ALPHA-ERASE",
        authorized_by="ledger_operator",
        apply=True,
        provider_case_ids={"whatsapp": "WABA-123", "exotel": "EXO-456"},
    )

    # Export external erasure ledger
    ledger_file = tmp_path / "erasure_ledger.json"
    exported = await export_ledger(ledger_file)
    assert exported["total_requests"] >= 1
    assert exported["total_suppression_markers"] >= 1

    # Verify zero PII in the exported ledger file
    ledger_content = ledger_file.read_text(encoding="utf-8")
    assert phone_alpha not in ledger_content
    assert "Patient Alpha" not in ledger_content

    # Simulate Restore of older backup:
    # Older backup has Patient Alpha restored, and lacks the erasure suppression marker!
    assert saved_alpha_contact is not None
    assert saved_alpha_msg is not None
    await db["contacts"].insert_one(saved_alpha_contact)
    await db["messages"].insert_one(saved_alpha_msg)
    await db["erasure_suppression"].delete_many({"tenant_id": tenant_1})
    await db["erasure_requests"].delete_many({"tenant_id": tenant_1})

    # Verify patient Alpha was resurrected by the simulated backup restore
    assert await db["contacts"].find_one({"_id": "contact-alpha"}) is not None
    assert await is_suppressed(tenant_1, phone_alpha) is False

    # Now replay the external erasure ledger
    replay_report = await replay_ledger(ledger_file, tenant_id=tenant_1)
    assert replay_report["status"] == "success"
    assert replay_report["imported_suppression_markers"] >= 1
    assert replay_report["replayed_erasures"] >= 1

    # Verify Patient Alpha is completely re-erased!
    assert await db["contacts"].find_one({"_id": "contact-alpha"}) is None
    assert await db["messages"].find_one({"_id": "msg-alpha"}) is None
    assert await is_suppressed(tenant_1, phone_alpha) is True

    # Verify Patient Beta in Tenant 2 was untouched
    beta_contact = await db["contacts"].find_one({"_id": "contact-beta"})
    assert beta_contact is not None
    assert beta_contact["name"] == "Patient Beta"
    assert await db["messages"].find_one({"_id": "msg-beta"}) is not None

    # Verify ledger verification tool
    v_alpha = await verify_erasure_state(tenant_1, phone_alpha)
    assert v_alpha["verified"] is True
    assert v_alpha["contact_clean"] is True
    assert v_alpha["suppressed"] is True

    v_beta = await verify_erasure_state(tenant_2, phone_beta)
    assert v_beta["verified"] is False
    assert v_beta["contact_clean"] is False
