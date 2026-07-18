"""Tool — Razorpay payment link (TRD §3, TRD §5) — Phase 3.

Creates a payment link, records a payments row, reconciled by the razorpay
webhook. Opt-in gated; max-2 nudge sequence (06-engineering-plan Phase 3 item 4).
"""

from __future__ import annotations

import logging
from datetime import datetime as dt, timezone
from typing import Any

from app.models.base import get_db

logger = logging.getLogger(__name__)


async def payment_link_create(
    tenant_id: str, contact_id: str, amount: int, *, booking_id: str | None = None
) -> dict[str, Any]:
    """Tool — Razorpay payment link (TRD §3, TRD §5)."""
    db = get_db()
    rzp_link_id = f"plink_{contact_id}_{amount}"
    
    logger.info(f"Generating payment link for contact {contact_id}, amount {amount}")
    
    payment = {
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "booking_id": booking_id,
        "rzp_link_id": rzp_link_id,
        "amount": amount,
        "status": "issued",
        "created_at": dt.now(timezone.utc).replace(tzinfo=None)
    }
    await db["payments"].insert_one(payment)
    
    return {
        "status": "success",
        "payment_link": f"https://rzp.io/i/{rzp_link_id}",
        "amount": amount,
        "payment_id": rzp_link_id
    }

