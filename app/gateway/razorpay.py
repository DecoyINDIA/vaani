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
from app.billing.plans import plan_from_provider_id
from app.config import settings
from app.models.base import get_db, mongo_id_candidates
from app.models.collections import BillingSubscriptions, Bookings, Payments, Tenants

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def verify_razorpay_signature(body: bytes, signature: str | None) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256."""
    if not signature:
        return False
    if not settings.razorpay_webhook_secret:
        if settings.app_env in ("staging", "prod"):
            return False
        return settings.use_mock_adapters
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

    if event == "payment_link.paid":
        link_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        link_id = link_entity.get("id")
        if link_id:
            payment_record = await Payments.find_by_link_id_unscoped(link_id)
            if not payment_record:
                await get_db()["payment_reconciliation"].insert_one(
                    {
                        "tenant_id": "SYSTEM",
                        "event": event,
                        "rzp_link_id": link_id,
                        "provider_payment_id": payment_entity.get("id"),
                        "status": "unknown_link",
                        "created_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                )
                return Response(content='{"status":"reconciliation_required"}', status_code=202)

            tenant_id = payment_record["tenant_id"]
            expected = {
                "amount": payment_record.get("amount"),
                "currency": payment_record.get("currency"),
                "reference_id": payment_record.get("reference_id"),
                "account_id": payment_record.get("provider_account_id"),
            }
            actual = {
                "amount": link_entity.get("amount"),
                "currency": link_entity.get("currency"),
                "reference_id": link_entity.get("reference_id"),
                "account_id": payload.get("account_id"),
            }
            errors = [
                key
                for key, value in expected.items()
                if value is not None and actual.get(key) != value
            ]
            if payment_entity.get("status") not in {"captured", None}:
                errors.append("payment_status")
            booking_id = payment_record.get("booking_id")
            booking = (
                await Bookings(tenant_id).find_one(
                    {"_id": {"$in": mongo_id_candidates(str(booking_id))}}
                )
                if booking_id
                else None
            )
            if booking and booking.get("status") == "cancelled":
                errors.append("cancelled_booking")

            if errors:
                await Payments(tenant_id).update_one(
                    {"rzp_link_id": link_id},
                    {
                        "$set": {
                            "status": "reconciliation_required",
                            "reconciliation_errors": sorted(set(errors)),
                        }
                    },
                )
                await audit.record(
                    tenant_id,
                    actor="system",
                    event_type="payment_reconciliation_required",
                    payload={"rzp_link_id": link_id, "errors": sorted(set(errors))},
                )
                return Response(content='{"status":"reconciliation_required"}', status_code=202)

            provider_payment_id = payment_entity.get("id")
            if payment_record.get("status") == "paid":
                if payment_record.get("provider_payment_id") == provider_payment_id:
                    return Response(content='{"status":"duplicate"}', status_code=200)
                return Response(content='{"status":"reconciliation_required"}', status_code=202)

            result = await Payments(tenant_id).update_one(
                {"rzp_link_id": link_id, "status": "issued"},
                {
                    "$set": {
                        "status": "paid",
                        "provider_payment_id": provider_payment_id,
                        "paid_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                },
            )
            if result.modified_count == 1:
                await audit.record(
                    tenant_id,
                    actor="system",
                    event_type="payment_completed",
                    payload={
                        "rzp_link_id": link_id,
                        "provider_payment_id": provider_payment_id,
                        "amount": payment_record.get("amount"),
                    },
                )

    elif event in {
        "subscription.activated",
        "subscription.charged",
        "subscription.resumed",
        "subscription.pending",
        "subscription.halted",
        "subscription.paused",
        "subscription.cancelled",
        "subscription.completed",
    }:
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        notes = sub_entity.get("notes", {})
        tenant_id = notes.get("tenant_id")
        provider_plan_id = sub_entity.get("plan_id")
        provider_subscription_id = sub_entity.get("id")
        if not tenant_id or not provider_subscription_id or not provider_plan_id:
            return Response(content='{"status":"reconciliation_required"}', status_code=202)
        try:
            plan = plan_from_provider_id(str(provider_plan_id))
        except ValueError:
            logger.error("Unknown Razorpay plan ID: %s", provider_plan_id)
            return Response(content='{"status":"reconciliation_required"}', status_code=202)

        billing_status = {
            "subscription.activated": "active",
            "subscription.charged": "active",
            "subscription.resumed": "active",
            "subscription.pending": "past_due",
            "subscription.halted": "past_due",
            "subscription.paused": "paused",
            "subscription.cancelled": "cancelled",
            "subscription.completed": "cancelled",
        }[event]
        subscriptions = BillingSubscriptions(str(tenant_id))
        existing = await subscriptions.find_one(
            {"provider_subscription_id": provider_subscription_id}
        )
        if (
            existing
            and existing.get("last_event") == event
            and existing.get("provider_status") == sub_entity.get("status")
        ):
            return Response(content='{"status":"duplicate"}', status_code=200)

        await subscriptions.find_one_and_update(
            {"provider_subscription_id": provider_subscription_id},
            {
                "$set": {
                    "provider_plan_id": provider_plan_id,
                    "plan": plan.code,
                    "billing_status": billing_status,
                    "provider_status": sub_entity.get("status"),
                    "last_event": event,
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            },
            upsert=True,
        )
        await Tenants.update_tenant_plan(str(tenant_id), plan.code, billing_status)
        await audit.record(
            str(tenant_id),
            actor="system",
            event_type="subscription_updated",
            payload={
                "subscription_id": provider_subscription_id,
                "provider_plan_id": provider_plan_id,
                "plan": plan.code,
                "billing_status": billing_status,
            },
        )

    return Response(content='{"status":"accepted"}', status_code=200)
