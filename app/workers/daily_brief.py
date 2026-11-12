"""Reporting agent — the owner's daily brief (F-13).

Each morning at 08:00 tenant-local time, sends the owner a WhatsApp utility
template summarising yesterday: conversations, bookings, bookings recovered
and their estimated value, and escalations still waiting for a person.

Idempotent per tenant per local day (operation_key), so the 15-minute
scheduler can scan freely. A tenant opts out with ``daily_brief_enabled: false``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import audit
from app.channels.whatsapp import send_template
from app.models.collections import Escalations, Tenants, Users
from app.reporting import avg_booking_value, window_metrics

logger = logging.getLogger(__name__)

SEND_HOUR = 8


async def _send_tenant_brief(tenant: dict[str, Any], now: datetime) -> None:
    tenant_id = str(tenant["_id"])
    if tenant.get("status", "active") != "active":
        return
    if tenant.get("daily_brief_enabled") is False:
        return
    zone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
    local_now = now.astimezone(zone)
    if local_now.hour != SEND_HOUR:
        return

    day = (local_now - timedelta(days=1)).date()
    day_key = day.isoformat()
    owner = await Users(tenant_id).find_one({"role": "owner", "status": "active"})
    owner_wa_id = (owner or {}).get("wa_id") or (owner or {}).get("phone")
    if not owner_wa_id:
        await audit.record(
            tenant_id,
            actor="system",
            event_type="operational_alert",
            operation_key=f"daily-brief-missing-recipient:{day_key}",
            payload={"kind": "daily_brief_missing_recipient", "day": day_key},
        )
        return

    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    metrics = await window_metrics(
        tenant,
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )
    open_escalations = await Escalations(tenant_id).count_documents({"status": "open"})

    await send_template(
        tenant_id=tenant_id,
        wa_id=str(owner_wa_id),
        template="daily_brief_owner",
        variables={
            "owner_name": str(tenant.get("name", "Owner")),
            "date_str": day.strftime("%a, %d %b"),
            "convs_count": str(metrics["conversations"]),
            "confirmed_count": str(metrics["confirmed"]),
            "recovered_count": str(metrics["recovered"]),
            "revenue_str": f"Rs. {metrics['recovered'] * avg_booking_value(tenant)}",
            "open_escalations": str(open_escalations),
        },
        operation_key=f"daily-brief:{tenant_id}:{day_key}",
    )


async def run_daily_briefs(*, now: datetime | None = None) -> None:
    """Send each tenant's brief during its own 08:00 hour; one tenant's failure is isolated."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    for tenant in await Tenants.all():
        tenant_id = str(tenant["_id"])
        try:
            await _send_tenant_brief(tenant, instant)
        except Exception as exc:
            day_key = instant.strftime("%Y-%m-%d")
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                operation_key=f"daily-brief-failed:{day_key}",
                payload={
                    "kind": "daily_brief_failed",
                    "day": day_key,
                    "error_type": type(exc).__name__,
                },
            )
            logger.exception("Daily brief failed for tenant %s", tenant_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_daily_briefs())


if __name__ == "__main__":
    main()
