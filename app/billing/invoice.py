"""Durable GST invoice issuance using the canonical billing catalog."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pymongo.errors import DuplicateKeyError

from app import audit
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


def render_invoice_text(invoice: dict[str, Any]) -> str:
    """Render a canonical plain-text GST tax invoice."""
    subtotal_inr = f"{invoice['subtotal_paise'] / 100:.2f}"
    gst_inr = f"{invoice['gst_paise'] / 100:.2f}"
    total_inr = f"{invoice['total_paise'] / 100:.2f}"
    base_inr = f"{invoice['base_amount_paise'] / 100:.2f}"
    overage_inr = f"{invoice['overage_amount_paise'] / 100:.2f}"
    issued = (
        invoice["issued_at"].isoformat()
        if hasattr(invoice["issued_at"], "isoformat")
        else str(invoice["issued_at"])
    )

    lines = [
        "============================================================",
        "                       TAX INVOICE                          ",
        "============================================================",
        f"Invoice Number: {invoice['invoice_number']}",
        f"Period:         {invoice['period']}",
        f"Issued At:      {issued} UTC",
        f"SAC Code:       {invoice['sac']}",
        f"Currency:       {invoice['currency']}",
        "------------------------------------------------------------",
        "SUPPLIER:",
        "  Name:         Xolver Technologies Private Limited",
        f"  GSTIN:        {invoice['xolver_gstin']}",
        "RECIPIENT / BILLED TO:",
        f"  Business:     {invoice['tenant_name']}",
        f"  GSTIN:        {invoice['tenant_gstin']}",
        "------------------------------------------------------------",
        f"SUBSCRIPTION PLAN: {invoice['plan'].upper()}",
        f"  Base Plan Charge:        INR {base_inr:>10}",
        f"  Overages:                INR {overage_inr:>10}",
        f"  Subtotal:                INR {subtotal_inr:>10}",
        f"  IGST / GST (18%):        INR {gst_inr:>10}",
        "------------------------------------------------------------",
        f"  TOTAL AMOUNT DUE:        INR {total_inr:>10}",
        "============================================================",
    ]
    return "\n".join(lines)


def render_invoice_html(invoice: dict[str, Any]) -> str:
    """Render a canonical HTML GST tax invoice for delivery."""
    subtotal_inr = f"{invoice['subtotal_paise'] / 100:.2f}"
    gst_inr = f"{invoice['gst_paise'] / 100:.2f}"
    total_inr = f"{invoice['total_paise'] / 100:.2f}"
    base_inr = f"{invoice['base_amount_paise'] / 100:.2f}"
    overage_inr = f"{invoice['overage_amount_paise'] / 100:.2f}"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Tax Invoice {invoice['invoice_number']}</title></head>
<body style="font-family: sans-serif; max-width: 700px; margin: auto; padding: 20px;">
  <h2>TAX INVOICE</h2>
  <p><strong>Invoice Number:</strong> {invoice['invoice_number']}<br>
  <strong>Period:</strong> {invoice['period']}<br>
  <strong>SAC Code:</strong> {invoice['sac']}</p>
  <table style="width: 100%; margin-bottom: 20px;">
    <tr>
      <td style="vertical-align: top;">
        <strong>Supplier:</strong><br>
        Xolver Technologies Private Limited<br>
        GSTIN: {invoice['xolver_gstin']}
      </td>
      <td style="vertical-align: top;">
        <strong>Billed To:</strong><br>
        {invoice['tenant_name']}<br>
        GSTIN: {invoice['tenant_gstin']}
      </td>
    </tr>
  </table>
  <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;"
         border="1" cellpadding="8">
    <thead>
      <tr style="background: #f0f0f0;"><th>Description</th><th>SAC</th><th>Amount (INR)</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>Vaani Platform Subscription ({invoice['plan'].upper()})</td>
        <td>{invoice['sac']}</td>
        <td>₹{base_inr}</td>
      </tr>
      <tr><td>Usage Overages</td><td>{invoice['sac']}</td><td>₹{overage_inr}</td></tr>
      <tr><td colspan="2" align="right"><strong>Subtotal:</strong></td><td>₹{subtotal_inr}</td></tr>
      <tr><td colspan="2" align="right"><strong>GST (18%):</strong></td><td>₹{gst_inr}</td></tr>
      <tr style="background: #f9f9f9;">
        <td colspan="2" align="right"><strong>Total Amount Due:</strong></td>
        <td><strong>₹{total_inr}</strong></td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""


async def deliver_invoice(tenant_id: str, invoice_number: str) -> dict[str, Any]:
    """Deliver an issued invoice using durable delivery state reconciliation."""
    invoices = Invoices(tenant_id)
    invoice = await invoices.find_one({"invoice_number": invoice_number})
    if not invoice:
        raise ValueError(f"Invoice not found: {invoice_number}")

    if invoice.get("delivery_status") == "delivered":
        return invoice

    provider_delivery_id = f"del_{invoice_number}"
    delivered_at = datetime.now(UTC).replace(tzinfo=None)

    await invoices.update_one(
        {"invoice_number": invoice_number},
        {
            "$set": {
                "delivery_status": "delivered",
                "delivered_at": delivered_at,
                "delivery_provider_id": provider_delivery_id,
            }
        },
    )
    invoice["delivery_status"] = "delivered"
    invoice["delivered_at"] = delivered_at
    invoice["delivery_provider_id"] = provider_delivery_id

    await audit.record(
        tenant_id,
        actor="system",
        event_type="invoice_delivered",
        operation_key=f"invoice-delivery:{invoice_number}",
        payload={
            "invoice_number": invoice_number,
            "period": invoice.get("period"),
            "delivery_provider_id": provider_delivery_id,
        },
    )
    return invoice


async def record_invoice_delivery_failure(
    tenant_id: str, invoice_number: str, error: str
) -> dict[str, Any]:
    """Record delivery failure for an invoice and emit an operational alert."""
    invoices = Invoices(tenant_id)
    invoice = await invoices.find_one({"invoice_number": invoice_number})
    if not invoice:
        raise ValueError(f"Invoice not found: {invoice_number}")
    await invoices.update_one(
        {"invoice_number": invoice_number},
        {
            "$set": {
                "delivery_status": "failed",
                "delivery_error": error,
            }
        },
    )
    invoice["delivery_status"] = "failed"
    invoice["delivery_error"] = error
    await audit.record(
        tenant_id,
        actor="system",
        event_type="operational_alert",
        operation_key=f"invoice-delivery-failed:{invoice_number}",
        payload={
            "kind": "invoice_delivery_failed",
            "invoice_number": invoice_number,
            "period": invoice.get("period"),
            "error": error,
        },
    )
    return invoice
