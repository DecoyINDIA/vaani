"""GST tax invoice generation (F-17, 06-engineering-plan Phase 3 item 2).

Xolver GSTIN + SAC (998314) + 18% + clinic GSTIN, auto-delivered monthly. Live
before the first paid invoice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from app.config import settings
from app.models.collections import Tenants, UsageMeters


async def generate_invoice(tenant_id: str, period: str) -> dict:
    """Generate GST tax invoice for the tenant for the given period (YYYY-MM)."""
    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")

    usage = await UsageMeters(tenant_id).find_one({"period": period})

    plan = tenant.get("plan", "starter").lower()

    if plan == "pro":
        base_amount = 4999.0
        # Voice overage calculation:
        # First 300 minutes are free. Overage rate: ₹2.0/min
        voice_minutes = usage.get("voice_minutes", 0) if usage else 0
        overage_minutes = max(0, voice_minutes - 300)
        overage_amount = overage_minutes * 2.0
    else:
        # Starter plan or fallback
        base_amount = 2999.0
        overage_amount = 0.0

    subtotal = base_amount + overage_amount
    gst_rate = 0.18
    gst_amount = round(subtotal * gst_rate, 2)
    total_amount = round(subtotal + gst_amount, 2)

    # Format period to clean string (e.g. "202607")
    clean_period = period.replace("-", "")

    invoice = {
        "invoice_number": f"INV-{tenant_id[:4].upper()}-{clean_period}",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "period": period,
        "tenant_name": tenant.get("name", "Unknown Clinic"),
        "tenant_gstin": tenant.get("gstin", ""),
        "xolver_gstin": settings.xolver_gstin or "27AAAAA1111A1Z1",
        "sac": settings.invoice_sac_code or "998314",
        "base_amount": subtotal,
        "gst_amount": gst_amount,
        "total_amount": total_amount
    }
    return invoice
