"""Durable GST invoice issuance using the canonical billing catalog."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.billing.meters import usage_for_period
from app.billing.plans import Plan, get_plan
from app.config import settings
from app.models.collections import Invoices, Tenants

_PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _overage_paise(plan: Plan, usage: dict[str, int]) -> int:
    amount = 0
    if plan.included_conversations is not None:
        excess = max(0, usage.get("wa_conversations", 0) - plan.included_conversations)
        amount += excess * plan.conversation_overage_paise
    if plan.included_bookings is not None:
        excess = max(0, usage.get("confirmed_bookings", 0) - plan.included_bookings)
        amount += excess * plan.booking_overage_paise
    if plan.included_voice_seconds is not None:
        excess_seconds = max(
            0, usage.get("voice_audio_seconds", 0) - plan.included_voice_seconds
        )
        started_minutes = (excess_seconds + 59) // 60
        amount += started_minutes * plan.voice_overage_paise_per_minute
    return amount


async def generate_invoice(tenant_id: str, period: str) -> dict[str, Any]:
    """Issue at most one invoice for a tenant/month and return its snapshot."""
    if not _PERIOD.fullmatch(period):
        raise ValueError("period must be YYYY-MM")
    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")
    if not tenant.get("name") or not tenant.get("gstin"):
        raise ValueError("Tenant billing name and GSTIN are required")
    if not settings.xolver_gstin:
        raise ValueError("XOLVER_GSTIN is required for invoice issuance")

    invoices = Invoices(tenant_id)
    existing = await invoices.find_one({"period": period})
    if existing:
        return existing

    plan = get_plan(str(tenant.get("plan", "")))
    usage = await usage_for_period(tenant_id, period)
    overage_paise = _overage_paise(plan, usage)
    subtotal_paise = plan.monthly_price_paise + overage_paise
    gst_paise = int(
        (Decimal(subtotal_paise) * Decimal("0.18")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    tenant_key = hashlib.sha256(tenant_id.encode()).hexdigest()[:10].upper()
    invoice: dict[str, Any] = {
        "invoice_number": f"INV-{period.replace('-', '')}-{tenant_key}",
        "period": period,
        "issued_at": datetime.now(UTC).replace(tzinfo=None),
        "tenant_name": tenant["name"],
        "tenant_gstin": tenant["gstin"],
        "xolver_gstin": settings.xolver_gstin,
        "sac": settings.invoice_sac_code,
        "currency": "INR",
        "plan": plan.code,
        "usage": usage,
        "base_amount_paise": plan.monthly_price_paise,
        "overage_amount_paise": overage_paise,
        "subtotal_paise": subtotal_paise,
        "gst_paise": gst_paise,
        "total_paise": subtotal_paise + gst_paise,
        "status": "issued",
        "delivery_status": "pending",
    }
    try:
        await invoices.insert_one(invoice)
    except DuplicateKeyError:
        concurrent = await invoices.find_one({"period": period})
        if concurrent:
            return concurrent
        raise
    return invoice
