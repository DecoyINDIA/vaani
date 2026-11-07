from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from app.agent.tools.payment_link_create import payment_link_create
from app.config import settings
from app.gateway.razorpay import verify_razorpay_signature
from app.main import app
from app.models.base import get_db
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parent / "fixtures" / "razorpay" / "payment_link_paid.json"


async def test_payment_link_create_is_provider_shaped_and_idempotent() -> None:
    db = get_db()
    tenant_id = "t_payment_link"
    await db["tenants"].insert_one({"_id": tenant_id, "name": "Synthetic Clinic"})
    await db["contacts"].insert_one(
        {
            "_id": "payment-contact",
            "tenant_id": tenant_id,
            "name": "Synthetic Patient",
            "phone": "955555555555",
        }
    )
    await db["bookings"].insert_one(
        {
            "_id": "payment-booking",
            "tenant_id": tenant_id,
            "contact_id": "payment-contact",
            "status": "confirmed",
        }
    )

    first = await payment_link_create(
        tenant_id,
        "payment-contact",
        50000,
        booking_id="payment-booking",
        request_id="payment-request",
    )
    repeated = await payment_link_create(
        tenant_id,
        "payment-contact",
        50000,
        booking_id="payment-booking",
        request_id="payment-request",
    )
    assert first["payment_id"].startswith("plink_")
    assert first["payment_link"].startswith("https://rzp.io/i/")
    assert first["amount"] == 50000
    assert repeated["deduplicated"] is True
    assert await db["payments"].count_documents({"tenant_id": tenant_id}) == 1

    with pytest.raises(ValueError, match="positive integer"):
        await payment_link_create(
            tenant_id,
            "payment-contact",
            0,
            request_id="invalid-amount",
        )


def test_signature_uses_exact_raw_body() -> None:
    old_secret = settings.razorpay_webhook_secret
    settings.razorpay_webhook_secret = "synthetic-secret"
    body = b'{"event":"payment_link.paid","spacing":"preserved"}'
    signature = hmac.new(
        b"synthetic-secret", body, digestmod=hashlib.sha256
    ).hexdigest()
    try:
        assert verify_razorpay_signature(body, signature) is True
        assert verify_razorpay_signature(body + b" ", signature) is False
    finally:
        settings.razorpay_webhook_secret = old_secret


async def test_late_payment_after_cancellation_requires_reconciliation() -> None:
    db = get_db()
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tenant_id = "t_late_payment"
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Synthetic Clinic",
            "razorpay_account_id": "acc_synthetic",
        }
    )
    await db["bookings"].insert_one(
        {
            "_id": "cancelled-booking",
            "tenant_id": tenant_id,
            "status": "cancelled",
        }
    )
    await db["payments"].insert_one(
        {
            "tenant_id": tenant_id,
            "booking_id": "cancelled-booking",
            "rzp_link_id": "plink_synthetic",
            "amount": 50000,
            "currency": "INR",
            "reference_id": "vaani_synthetic_reference",
            "provider_account_id": "acc_synthetic",
            "status": "issued",
        }
    )

    response = TestClient(app).post(
        "/webhooks/razorpay",
        content=json.dumps(payload, separators=(",", ":")),
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "synthetic-test-signature",
        },
    )
    assert response.status_code == 202
    payment = await db["payments"].find_one({"rzp_link_id": "plink_synthetic"})
    booking = await db["bookings"].find_one({"_id": "cancelled-booking"})
    assert payment["status"] == "reconciliation_required"
    assert "cancelled_booking" in payment["reconciliation_errors"]
    assert booking["status"] == "cancelled"
