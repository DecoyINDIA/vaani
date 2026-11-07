"""Replay-safe usage events with explicit units and tenant-local periods."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.collections import Tenants, UsageEvents, UsageMeters

METRIC_UNITS = {
    "confirmed_bookings": "booking",
    "llm_input_tokens": "token",
    "llm_output_tokens": "token",
    "meta_billable_messages": "message",
    "wa_conversations": "conversation",
    "voice_audio_seconds": "second",
}


async def record_usage(
    tenant_id: str,
    *,
    event_id: str,
    metric: str,
    quantity: int,
    occurred_at: datetime | None = None,
) -> bool:
    """Record one immutable usage event; return false for a replay."""
    if not event_id:
        raise ValueError("event_id is required")
    if metric not in METRIC_UNITS:
        raise ValueError(f"Unknown usage metric: {metric}")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError("quantity must be a non-negative integer")

    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")
    timezone_name = str(tenant.get("timezone", "Asia/Kolkata"))
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Unknown tenant timezone: {timezone_name}") from None

    instant = occurred_at or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    instant_utc = instant.astimezone(UTC)
    period = instant_utc.astimezone(timezone).strftime("%Y-%m")
    result = await UsageEvents(tenant_id).find_one_and_update(
        {"event_id": event_id},
        {
            "$setOnInsert": {
                "metric": metric,
                "unit": METRIC_UNITS[metric],
                "quantity": quantity,
                "period": period,
                "occurred_at": instant_utc.replace(tzinfo=None),
            }
        },
        upsert=True,
    )
    if result is not None:
        return False

    await UsageMeters(tenant_id).find_one_and_update(
        {"period": period},
        {"$inc": {metric: quantity}},
        upsert=True,
    )
    return True


async def usage_for_period(tenant_id: str, period: str) -> dict[str, int]:
    """Rebuild authoritative totals from immutable events, not the cache."""
    totals: dict[str, int] = {}
    async for event in UsageEvents(tenant_id).find({"period": period}):
        metric = str(event["metric"])
        totals[metric] = totals.get(metric, 0) + int(event["quantity"])
    return totals
