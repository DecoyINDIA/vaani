"""Weekly ROI summary worker (F-13) — THE retention product.

Computes recovered bookings (after-hours + busy-line + previously-missed numbers),
revenue estimate, containment; sends owner WhatsApp template. Ships BEFORE any
billing code (06-engineering-plan Phase 3 item 1).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import audit
from app.channels.whatsapp import send_template
from app.models.collections import Tenants, Users
from app.reporting import avg_booking_value, window_metrics

logger = logging.getLogger(__name__)


async def _send_tenant_summary(tenant: dict[str, Any], now: datetime) -> None:
    tenant_id = str(tenant["_id"])
    timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
    local_now = now.astimezone(timezone)
    if local_now.weekday() != 6 or local_now.hour != 23:
        return

    week = local_now.strftime("%G-%V")
    owner = await Users(tenant_id).find_one({"role": "owner", "status": "active"})
    owner_wa_id = (owner or {}).get("wa_id") or (owner or {}).get("phone")
    if not owner_wa_id:
        await audit.record(
            tenant_id,
            actor="system",
            event_type="operational_alert",
            operation_key=f"weekly-summary-missing-recipient:{week}",
            payload={"kind": "weekly_summary_missing_recipient", "week": week},
        )
        return

    local_start = local_now - timedelta(days=7)
    start_date = local_start.astimezone(UTC).replace(tzinfo=None)
    end_date = now.astimezone(UTC).replace(tzinfo=None)
    metrics = await window_metrics(tenant, start_date, end_date)

    variables = {
        "owner_name": str(tenant.get("name", "Owner")),
        "date_range_str": (
            f"{local_start.strftime('%b %d')} - {local_now.strftime('%b %d')}"
        ),
        "convs_count": str(metrics["conversations"]),
        "confirmed_count": str(metrics["confirmed"]),
        "recovered_count": str(metrics["recovered"]),
        "revenue_str": f"Rs. {metrics['recovered'] * avg_booking_value(tenant)}",
    }
    await send_template(
        tenant_id=tenant_id,
        wa_id=str(owner_wa_id),
        template="weekly_summary_owner",
        variables=variables,
        operation_key=f"weekly-summary:{tenant_id}:{week}",
    )


async def run_weekly_summaries(*, now: datetime | None = None) -> None:
    """Send each tenant's summary during its own Sunday 23:00 hour."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    for tenant in await Tenants.all():
        tenant_id = str(tenant["_id"])
        try:
            await _send_tenant_summary(tenant, instant)
        except Exception as exc:
            error_type = type(exc).__name__
            week = instant.strftime("%G-%V")
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                operation_key=f"weekly-summary-failed:{week}",
                payload={
                    "kind": "weekly_summary_failed",
                    "week": week,
                    "error_type": error_type,
                },
            )
            logger.exception("Weekly summary failed for tenant %s", tenant_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting weekly summary worker scan...")
    asyncio.run(run_weekly_summaries())
    logger.info("Weekly summary worker scan completed.")


if __name__ == "__main__":
    main()
