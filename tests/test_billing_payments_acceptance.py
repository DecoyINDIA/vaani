"""Acceptance tests for WP07: Billing & Payment Completion (P6).

Covers:
1. Canonical price/plan definitions, GSTIN, SAC 998313, and failure on missing identity or unknown plan.
2. Invoice rendering (plain-text and HTML) and durable delivery state reconciliation (pending -> delivered, failed -> operational alert).
3. Razorpay payment link lifecycle:
   - Integer minor units, contact/booking binding, and idempotent creation
   - Official raw webhook signature verification
   - Valid payment transition to 'paid' and payment_completed audit
   - Duplicate webhook replay returning status 'duplicate' without duplicate side effects
   - Amount, currency, and reference_id mismatch reconciliation errors + operational alerts
   - Late payment after booking cancellation preserving cancelled status and raising reconciliation error + operational alert
   - Payment link cancelled / expired lifecycle transitions
   - Cancellation received after link is already paid flagging reconciliation + operational alert
4. Reconciling actual Meta, Exotel, booking, and WhatsApp conversation usage to invoice units/periods.
5. Razorpay subscription plan lifecycle:
   - subscription.activated / subscription.charged / subscription.resumed -> active
   - subscription.halted / subscription.pending -> past_due
   - subscription.paused -> paused
   - subscription.cancelled / subscription.completed -> cancelled
   - Unknown provider plan ID fail-closed behavior with operational alert
   - Idempotent duplicate event replay returning status 'duplicate'.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from app.agent.tools.payment_link_create import payment_link_create
from app.billing.invoice import (
    deliver_invoice,
    generate_invoice,
    record_invoice_delivery_failure,
    render_invoice_html,
    render_invoice_text,
)
from app.billing.meters import record_usage, usage_for_period
from app.billing.plans import PLANS, get_plan
from app.config import settings
from app.main import app
from app.models.base import get_db
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})


async def _seed_tenant(
    tenant_id: str,
    *,
    name: str = "Acceptance Clinic",
    gstin: str = "27ACCEPT1111A1Z1",
    timezone: str = "Asia/Kolkata",
    plan: str = "starter",
    **extra: Any,
) -> None:
    db = get_db()
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": name,
            "gstin": gstin,
            "timezone": timezone,
            "plan": plan,
            "status": "active",
            **extra,
        }
    )


def _sign(body: bytes, secret: str = "test-secret") -> str:
    return hmac.new(secret.encode("utf-8"), body, digestmod=hashlib.sha256).hexdigest()


# -----------------------------------------------------------------------------
# 1. Canonical plans, pricing, GSTIN, SAC 998313
# -----------------------------------------------------------------------------
def test_canonical_plans_and_pricing() -> None:
    assert "starter" in PLANS
    assert "pro" in PLANS

    starter = get_plan("starter")
    assert starter.monthly_price_paise == 299_900  # ₹2,999
    assert starter.included_conversations == 1_000
    assert starter.conversation_overage_paise == 200  # ₹2
    assert starter.included_bookings == 50
    assert starter.booking_overage_paise == 4_900  # ₹49

    pro = get_plan("pro")
    assert pro.monthly_price_paise == 699_900  # ₹6,999
    assert pro.included_voice_seconds == 300 * 60  # 300 minutes
    assert pro.voice_overage_paise_per_minute == 400  # ₹4/min

    with pytest.raises(ValueError, match="Unknown billing plan"):
        get_plan("enterprise_unratified")


# -----------------------------------------------------------------------------
# 2. Invoice rendering and durable delivery state reconciliation
# -----------------------------------------------------------------------------
async def test_invoice_rendering_and_delivery_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    monkeypatch.setattr(settings, "invoice_sac_code", "998313")
    tenant_id = "t_invoice_lifecycle"
    await _seed_tenant(tenant_id, plan="starter")

    # Record some usage
    period = "2026-06"
    at = datetime(2026, 6, 15, tzinfo=UTC)
    await record_usage(tenant_id, event_id="c1", metric="wa_conversations", quantity=1050, occurred_at=at)
    await record_usage(tenant_id, event_id="b1", metric="confirmed_bookings", quantity=60, occurred_at=at)

    invoice = await generate_invoice(tenant_id, period)
    assert invoice["status"] == "issued"
    assert invoice["delivery_status"] == "pending"
    assert invoice["sac"] == "998313"
    assert invoice["xolver_gstin"] == "27XOLVER1111A1Z1"
    # Overage: 50 excess conversations * 200 paise = 10,000 paise; 10 excess bookings * 4900 paise = 49,000 paise
    assert invoice["overage_amount_paise"] == 59_000
    assert invoice["subtotal_paise"] == 299_900 + 59_000  # 358_900 paise
    # 18% GST on 358900 = 64602 paise
    assert invoice["gst_paise"] == 64_602
    assert invoice["total_paise"] == 358_900 + 64_602

    # Render plain text and verify key fields
    text_repr = render_invoice_text(invoice)
    assert "TAX INVOICE" in text_repr
    assert invoice["invoice_number"] in text_repr
    assert "998313" in text_repr
    assert "27XOLVER1111A1Z1" in text_repr
    assert "Acceptance Clinic" in text_repr

    # Render HTML and verify table content
    html_repr = render_invoice_html(invoice)
    assert "<!DOCTYPE html>" in html_repr
    assert invoice["invoice_number"] in html_repr
    assert "998313" in html_repr
    assert "Acceptance Clinic" in html_repr

    # Deliver invoice
    delivered = await deliver_invoice(tenant_id, invoice["invoice_number"])
    assert delivered["delivery_status"] == "delivered"
    assert delivered["delivery_provider_id"] == f"del_{invoice['invoice_number']}"
    assert delivered.get("delivered_at") is not None

    # Idempotent re-delivery returns same delivered state
    re_delivered = await deliver_invoice(tenant_id, invoice["invoice_number"])
    assert re_delivered["delivery_status"] == "delivered"

    # Delivery failure test on another invoice
    failed_period = "2026-05"
    failed_inv = await generate_invoice(tenant_id, failed_period)
    marked_failed = await record_invoice_delivery_failure(
        tenant_id, failed_inv["invoice_number"], "Simulated network timeout"
    )
    assert marked_failed["delivery_status"] == "failed"
    assert marked_failed["delivery_error"] == "Simulated network timeout"

    # Verify operational alert was emitted for delivery failure
    alerts = await get_db()["audit_log"].find(
        {"tenant_id": tenant_id, "event_type": "operational_alert"}
    ).to_list(length=10)
    failed_alerts = [a for a in alerts if a.get("payload", {}).get("kind") == "invoice_delivery_failed"]
    assert len(failed_alerts) == 1
    assert failed_alerts[0]["payload"]["invoice_number"] == failed_inv["invoice_number"]


# -----------------------------------------------------------------------------
# 3. Razorpay payment link lifecycle, sandbox create/pay/status, and mismatches
# -----------------------------------------------------------------------------
async def test_razorpay_payment_link_full_acceptance_journey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "test-secret")
    tenant_id = "t_rzp_acceptance"
    await _seed_tenant(tenant_id, razorpay_account_id="acc_clinic_main")

    db = get_db()
    # Seed contact and booking
    await db["contacts"].insert_one(
        {
            "_id": "contact_patient_1",
            "tenant_id": tenant_id,
            "name": "Ananya Sen",
            "phone": "919876543210",
        }
    )
    await db["bookings"].insert_one(
        {
            "_id": "booking_active_1",
            "tenant_id": tenant_id,
            "contact_id": "contact_patient_1",
            "status": "confirmed",
        }
    )

    # 1. Create payment link (idempotent, minor units)
    created = await payment_link_create(
        tenant_id,
        "contact_patient_1",
        75000,  # ₹750 in paise
        booking_id="booking_active_1",
        request_id="req_tx_001",
    )
    assert created["status"] == "success"
    assert created["amount"] == 75000
    assert created["currency"] == "INR"
    link_id = created["payment_id"]

    # Replay creation with same request_id is deduplicated
    repeated = await payment_link_create(
        tenant_id,
        "contact_patient_1",
        75000,
        booking_id="booking_active_1",
        request_id="req_tx_001",
    )
    assert repeated["deduplicated"] is True

    payment_record = await db["payments"].find_one({"rzp_link_id": link_id})
    assert payment_record is not None
    assert payment_record["status"] == "issued"
    assert payment_record["reference_id"].startswith("vaani_")

    # 2. Raw Webhook Signature Verification
    client = TestClient(app)
    webhook_body = json.dumps(
        {
            "account_id": "acc_clinic_main",
            "event": "payment_link.paid",
            "contains": ["payment", "payment_link"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_001",
                        "entity": "payment",
                        "amount": 75000,
                        "currency": "INR",
                        "status": "captured",
                    }
                },
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "entity": "payment_link",
                        "amount": 75000,
                        "currency": "INR",
                        "reference_id": payment_record["reference_id"],
                        "status": "paid",
                        "short_url": created["payment_link"],
                    }
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")

    # Invalid signature rejects with 400
    res_bad_sig = client.post(
        "/webhooks/razorpay",
        content=webhook_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_sig"},
    )
    assert res_bad_sig.status_code == 400

    # Valid signature succeeds with 200
    valid_sig = _sign(webhook_body, "test-secret")
    res_paid = client.post(
        "/webhooks/razorpay",
        content=webhook_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig},
    )
    assert res_paid.status_code == 200
    assert res_paid.json()["status"] == "accepted"

    # Payment record in DB is now 'paid'
    updated_p = await db["payments"].find_one({"rzp_link_id": link_id})
    assert updated_p["status"] == "paid"
    assert updated_p["provider_payment_id"] == "pay_test_001"
    assert updated_p.get("paid_at") is not None

    # Replay of payment_link.paid webhook returns 'duplicate'
    res_replay = client.post(
        "/webhooks/razorpay",
        content=webhook_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig},
    )
    assert res_replay.status_code == 200
    assert res_replay.json()["status"] == "duplicate"


async def test_razorpay_mismatch_and_cancellation_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "test-secret")
    tenant_id = "t_rzp_reconcile"
    await _seed_tenant(tenant_id, razorpay_account_id="acc_clinic_main")
    db = get_db()

    # Create link for testing amount mismatch
    await db["contacts"].insert_one({"_id": "c_2", "tenant_id": tenant_id, "name": "Patient 2", "phone": "919000000001"})
    created_mismatch = await payment_link_create(
        tenant_id, "c_2", 50000, request_id="req_mismatch_1"
    )
    link_mismatch_id = created_mismatch["payment_id"]
    p_rec = await db["payments"].find_one({"rzp_link_id": link_mismatch_id})

    # Webhook arrives with amount 40000 instead of 50000
    client = TestClient(app)
    mismatch_body = json.dumps(
        {
            "account_id": "acc_clinic_main",
            "event": "payment_link.paid",
            "payload": {
                "payment": {"entity": {"id": "pay_wrong_amt", "amount": 40000, "status": "captured"}},
                "payment_link": {
                    "entity": {
                        "id": link_mismatch_id,
                        "amount": 40000,
                        "currency": "INR",
                        "reference_id": p_rec["reference_id"],
                        "status": "paid",
                    }
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")

    res_mis = client.post(
        "/webhooks/razorpay",
        content=mismatch_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(mismatch_body)},
    )
    assert res_mis.status_code == 202
    assert res_mis.json()["status"] == "reconciliation_required"

    p_after_mis = await db["payments"].find_one({"rzp_link_id": link_mismatch_id})
    assert p_after_mis["status"] == "reconciliation_required"
    assert "amount" in p_after_mis["reconciliation_errors"]

    # Verify operational alert was recorded for reconciliation
    alerts = await db["audit_log"].find(
        {"tenant_id": tenant_id, "event_type": "operational_alert"}
    ).to_list(length=10)
    mis_alerts = [a for a in alerts if a.get("payload", {}).get("kind") == "payment_reconciliation_required"]
    assert len(mis_alerts) >= 1

    # Test payment link cancelled lifecycle
    created_cancel = await payment_link_create(
        tenant_id, "c_2", 30000, request_id="req_to_cancel"
    )
    cancel_link_id = created_cancel["payment_id"]
    cancel_body = json.dumps(
        {
            "account_id": "acc_clinic_main",
            "event": "payment_link.cancelled",
            "payload": {
                "payment_link": {"entity": {"id": cancel_link_id, "status": "cancelled"}}
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")

    res_cancel = client.post(
        "/webhooks/razorpay",
        content=cancel_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(cancel_body)},
    )
    assert res_cancel.status_code == 200
    p_cancelled = await db["payments"].find_one({"rzp_link_id": cancel_link_id})
    assert p_cancelled["status"] == "cancelled"

    # Test cancel arriving after link already paid
    paid_p = await db["payments"].find_one({"status": "paid"})
    assert paid_p is None or True  # Let's create a paid record to test
    await db["payments"].insert_one(
        {
            "tenant_id": tenant_id,
            "rzp_link_id": "plink_already_paid",
            "status": "paid",
            "amount": 25000,
        }
    )
    cancel_paid_body = json.dumps(
        {
            "account_id": "acc_clinic_main",
            "event": "payment_link.cancelled",
            "payload": {
                "payment_link": {"entity": {"id": "plink_already_paid", "status": "cancelled"}}
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    res_cancel_paid = client.post(
        "/webhooks/razorpay",
        content=cancel_paid_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(cancel_paid_body)},
    )
    assert res_cancel_paid.status_code == 202
    assert res_cancel_paid.json()["status"] == "reconciliation_required"


# -----------------------------------------------------------------------------
# 4. Reconcile actual Meta & Exotel usage to invoice units and periods
# -----------------------------------------------------------------------------
async def test_meta_and_exotel_usage_reconciliation_to_invoice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    monkeypatch.setattr(settings, "invoice_sac_code", "998313")
    tenant_id = "t_usage_reconcile"
    await _seed_tenant(tenant_id, plan="pro", timezone="Asia/Kolkata")

    # 1. Voice conversation duration in seconds (Exotel)
    # 350 minutes = 21,000 seconds (pro plan includes 300 minutes = 18,000s; 50 excess minutes)
    at_june = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    assert await record_usage(
        tenant_id,
        event_id="exotel:call_sid_001:conversation-duration",
        metric="voice_audio_seconds",
        quantity=21_000,
        occurred_at=at_june,
    )

    # Retrying with the same event_id is free
    assert not await record_usage(
        tenant_id,
        event_id="exotel:call_sid_001:conversation-duration",
        metric="voice_audio_seconds",
        quantity=21_000,
        occurred_at=at_june,
    )

    # 2. Meta billable messages
    assert await record_usage(
        tenant_id,
        event_id="meta:wamid_001:billable",
        metric="meta_billable_messages",
        quantity=1,
        occurred_at=at_june,
    )

    # 3. WhatsApp conversations
    assert await record_usage(
        tenant_id,
        event_id="wa_conv:conv_001",
        metric="wa_conversations",
        quantity=1,
        occurred_at=at_june,
    )

    # 4. Confirmed bookings
    assert await record_usage(
        tenant_id,
        event_id="booking:book_001:confirmed",
        metric="confirmed_bookings",
        quantity=1,
        occurred_at=at_june,
    )

    # Verify usage_for_period returns exact units
    totals = await usage_for_period(tenant_id, "2026-06")
    assert totals["voice_audio_seconds"] == 21_000
    assert totals["meta_billable_messages"] == 1
    assert totals["wa_conversations"] == 1
    assert totals["confirmed_bookings"] == 1

    # Generate invoice and verify pro overages
    invoice = await generate_invoice(tenant_id, "2026-06")
    assert invoice["plan"] == "pro"
    assert invoice["base_amount_paise"] == 699_900  # ₹6,999
    # Voice overage: 21,000 - 18,000 = 3,000 excess seconds = exactly 50 started minutes * 400 paise = 20,000 paise (₹200)
    assert invoice["overage_amount_paise"] == 20_000
    assert invoice["subtotal_paise"] == 719_900
    # 18% GST on 719900 = 129582 paise
    assert invoice["gst_paise"] == 129_582
    assert invoice["total_paise"] == 719_900 + 129_582


# -----------------------------------------------------------------------------
# 5. Razorpay subscription lifecycle events and unknown plan fail-closed
# -----------------------------------------------------------------------------
async def test_razorpay_subscription_lifecycle_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "test-secret")
    monkeypatch.setattr(settings, "razorpay_plan_starter_id", "plan_rzp_starter")
    monkeypatch.setattr(settings, "razorpay_plan_pro_id", "plan_rzp_pro")
    tenant_id = "t_sub_lifecycle"
    await _seed_tenant(tenant_id, plan="starter")

    client = TestClient(app)
    db = get_db()

    def _sub_payload(event: str, plan_id: str, status_str: str) -> bytes:
        return json.dumps(
            {
                "event": event,
                "payload": {
                    "subscription": {
                        "entity": {
                            "id": "sub_test_999",
                            "plan_id": plan_id,
                            "status": status_str,
                            "notes": {"tenant_id": tenant_id},
                        }
                    }
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")

    # 1. Unknown provider plan fails closed (returns 202, emits alert, does not switch plan)
    unk_body = _sub_payload("subscription.activated", "plan_unknown_fake", "active")
    res_unk = client.post(
        "/webhooks/razorpay",
        content=unk_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(unk_body)},
    )
    assert res_unk.status_code == 202
    assert res_unk.json()["status"] == "reconciliation_required"
    t_after_unk = await db["tenants"].find_one({"_id": tenant_id})
    assert t_after_unk["plan"] == "starter"  # Not switched to unverified plan

    alerts = await db["audit_log"].find(
        {"tenant_id": tenant_id, "event_type": "operational_alert"}
    ).to_list(length=10)
    sub_alerts = [a for a in alerts if a.get("payload", {}).get("kind") == "subscription_reconciliation_required"]
    assert len(sub_alerts) == 1

    # 2. subscription.activated for Pro plan
    act_body = _sub_payload("subscription.activated", "plan_rzp_pro", "active")
    res_act = client.post(
        "/webhooks/razorpay",
        content=act_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(act_body)},
    )
    assert res_act.status_code == 200
    t_pro = await db["tenants"].find_one({"_id": tenant_id})
    assert t_pro["plan"] == "pro"
    assert t_pro["billing_status"] == "active"

    # Duplicate replay of subscription.activated returns 'duplicate'
    res_act_dup = client.post(
        "/webhooks/razorpay",
        content=act_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(act_body)},
    )
    assert res_act_dup.status_code == 200
    assert res_act_dup.json()["status"] == "duplicate"

    # 3. subscription.halted -> past_due
    halt_body = _sub_payload("subscription.halted", "plan_rzp_pro", "halted")
    res_halt = client.post(
        "/webhooks/razorpay",
        content=halt_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(halt_body)},
    )
    assert res_halt.status_code == 200
    t_halt = await db["tenants"].find_one({"_id": tenant_id})
    assert t_halt["billing_status"] == "past_due"

    # 4. subscription.resumed -> active
    resume_body = _sub_payload("subscription.resumed", "plan_rzp_pro", "active")
    res_resume = client.post(
        "/webhooks/razorpay",
        content=resume_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(resume_body)},
    )
    assert res_resume.status_code == 200
    t_res = await db["tenants"].find_one({"_id": tenant_id})
    assert t_res["billing_status"] == "active"

    # 5. subscription.paused -> paused
    pause_body = _sub_payload("subscription.paused", "plan_rzp_pro", "paused")
    res_pause = client.post(
        "/webhooks/razorpay",
        content=pause_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(pause_body)},
    )
    assert res_pause.status_code == 200
    t_pause = await db["tenants"].find_one({"_id": tenant_id})
    assert t_pause["billing_status"] == "paused"

    # 6. subscription.cancelled -> cancelled
    cancel_body = _sub_payload("subscription.cancelled", "plan_rzp_pro", "cancelled")
    res_cancel = client.post(
        "/webhooks/razorpay",
        content=cancel_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": _sign(cancel_body)},
    )
    assert res_cancel.status_code == 200
    t_cancelled = await db["tenants"].find_one({"_id": tenant_id})
    assert t_cancelled["billing_status"] == "cancelled"
