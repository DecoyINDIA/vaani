"""Create and persist a Razorpay payment link using the official API contract."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings
from app.models.collections import Bookings, Contacts, Payments, Tenants


async def payment_link_create(
    tenant_id: str,
    contact_id: str,
    amount: int,
    *,
    request_id: str,
    booking_id: str | None = None,
    currency: str = "INR",
) -> dict[str, Any]:
    """Create an idempotent link; amount is always an integer minor unit."""
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("amount must be a positive integer in currency minor units")
    if currency != "INR":
        raise ValueError("only the configured INR account is supported")
    if not request_id:
        raise ValueError("request_id is required")

    existing = await Payments(tenant_id).find_one({"request_id": request_id})
    if existing:
        return {
            "status": "success",
            "payment_link": existing["provider_url"],
            "amount": existing["amount"],
            "currency": existing["currency"],
            "payment_id": existing["rzp_link_id"],
            "deduplicated": True,
        }

    try:
        contact_id_resolved = await Contacts(tenant_id).resolve_id(contact_id)
    except ValueError as e:
        raise ValueError(f"ambiguous contact: {e}") from e
    if contact_id_resolved is None:
        raise ValueError("contact not found")
    contact = await Contacts(tenant_id).find_one({"_id": contact_id_resolved})
    if not contact:
        raise ValueError("contact not found")
    booking = None
    if booking_id:
        try:
            booking_id_resolved = await Bookings(tenant_id).resolve_id(booking_id)
        except ValueError as e:
            raise ValueError(f"ambiguous booking: {e}") from e
        if booking_id_resolved is None:
            raise ValueError("booking not found for contact")
        booking = await Bookings(tenant_id).find_one(
            {
                "_id": booking_id_resolved,
                "contact_id": {"$in": [contact_id_resolved, contact_id, str(contact["_id"])]},
            }
        )
        if not booking:
            raise ValueError("booking not found for contact")

    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise ValueError("tenant not found")
    reference_id = "vaani_" + hashlib.sha256(
        f"{tenant_id}:{request_id}".encode()
    ).hexdigest()[:24]
    body: dict[str, Any] = {
        "amount": amount,
        "currency": currency,
        "reference_id": reference_id,
        "description": f"Appointment payment for {tenant.get('name', 'clinic')}",
        "customer": {
            "name": contact.get("name", "Patient"),
            "contact": contact.get("phone") or contact.get("wa_id"),
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {
            "tenant_id": tenant_id,
            "contact_id": str(contact["_id"]),
            "booking_id": booking_id or "",
        },
    }
    if not body["customer"]["contact"]:
        raise ValueError("contact has no payment phone number")

    if settings.use_mock_adapters:
        suffix = hashlib.sha256(request_id.encode()).hexdigest()[:12]
        data: dict[str, Any] = {
            "id": f"plink_{suffix}",
            "short_url": f"https://rzp.io/i/{suffix}",
            "amount": amount,
            "currency": currency,
            "reference_id": reference_id,
            "status": "created",
        }
    else:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.razorpay.com/v1/payment_links",
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                json=body,
                timeout=30.0,
            )
        response.raise_for_status()
        data = response.json()

    provider_id = data.get("id")
    provider_url = data.get("short_url")
    if (
        not provider_id
        or not provider_url
        or data.get("amount") != amount
        or data.get("currency") != currency
        or data.get("reference_id") != reference_id
    ):
        raise RuntimeError("Razorpay returned an invalid payment-link response")

    await Payments(tenant_id).insert_one(
        {
            "request_id": request_id,
            "contact_id": str(contact["_id"]),
            "booking_id": str(booking["_id"]) if booking else None,
            "rzp_link_id": provider_id,
            "provider_url": provider_url,
            "reference_id": reference_id,
            "provider_account_id": tenant.get("razorpay_account_id"),
            "amount": amount,
            "currency": currency,
            "status": "issued",
            "created_at": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    return {
        "status": "success",
        "payment_link": provider_url,
        "amount": amount,
        "currency": currency,
        "payment_id": provider_id,
    }
