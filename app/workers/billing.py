"""Monthly durable invoice issuance; delivery is reconciled separately."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app import audit
from app.billing.invoice import generate_invoice
from app.models.collections import Tenants

logger = logging.getLogger(__name__)


async def run_monthly_invoices(*, now: datetime | None = None) -> None:
    """Issue the previous local month's invoice on each tenant's first day."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    for tenant in await Tenants.all():
        tenant_id = str(tenant["_id"])
        period = instant.strftime("%Y-%m")
        try:
            local_now = instant.astimezone(
                ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
            )
            if local_now.day != 1:
                continue
            period = (local_now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            await generate_invoice(tenant_id, period)
        except Exception as exc:
            error_type = type(exc).__name__
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                operation_key=f"invoice-issuance-failed:{period}",
                payload={
                    "kind": "invoice_issuance_failed",
                    "period": period,
                    "error_type": error_type,
                },
            )
            logger.exception("Invoice issuance failed for tenant %s", tenant_id)
