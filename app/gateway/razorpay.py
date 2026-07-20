"""Razorpay webhook (TRD §5.1) — Phase 3.

POST /webhooks/razorpay — payment-link + subscription/mandate events,
signature-verified against RAZORPAY_WEBHOOK_SECRET. Reconciles payments and
UPI Autopay mandate lifecycle (06-engineering-plan Phase 3, item 2/4).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from app import audit
from app.config import settings
from app.models.collections import Bookings, Payments, Tenants

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def verify_razorpay_signature(body: bytes, signature: str | None) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256."""
    if not signature:
        return False
    if not settings.razorpay_webhook_secret:
        if settings.app_env in ("staging", "prod"):
            return False
        return True  # If no secret is configured, allow in dev/testing
    computed = hmac.new(
        key=settings.razorpay_webhook_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/razorpay")
async def receive(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not verify_razorpay_signature(body, signature):
        logger.warning("Invalid Razorpay webhook signature")
        return Response(content="Invalid signature", status_code=400)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(content="Malformed JSON", status_code=400)

    event = payload.get("event")
    logger.info(f"Received Razorpay webhook event: {event}")

    if event == "payment.link.paid":
        link_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
        link_id = link_entity.get("id")
        if link_id:
            payment_record = await Payments.find_by_link_id_unscoped(link_id)
            if payment_record:
                tenant_id = payment_record["tenant_id"]
                # Update payment status
                await Payments(tenant_id).update_one(
                    {"rzp_link_id": link_id},
                    {"$set": {
                        "status": "paid",
                        "paid_at": datetime.now(UTC).replace(tzinfo=None)
                    }}
                )
                
                # Update booking status if linked
                booking_id = payment_record.get("booking_id")
                if booking_id:
                    await Bookings(tenant_id).update_one(
                        {"_id": booking_id},
                        {"$set": {"status": "confirmed"}}
                    )

                # Record in audit log
                await audit.record(
                    tenant_id,
                    actor="system",
                    event_type="payment_completed",
                    payload={"rzp_link_id": link_id, "amount": payment_record.get("amount")},
                    conversation_id=None
                )

    elif event in ("subscription.activated", "subscription.charged"):
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        notes = sub_entity.get("notes", {})
        tenant_id = notes.get("tenant_id")
        plan_id = sub_entity.get("plan_id", "pro")
        
        if tenant_id:
            status = "active" if sub_entity.get("status") in ("active", "charged") else "active"
            await Tenants.update_tenant_plan(tenant_id, plan=plan_id, status=status)
            
            # Record in audit log
            await audit.record(
                tenant_id,
                actor="system",
                event_type="subscription_updated",
                payload={
                    "subscription_id": sub_entity.get("id"),
                    "plan": plan_id,
                    "status": status,
                },
                conversation_id=None
            )

    return Response(content='{"status":"accepted"}', status_code=200)
