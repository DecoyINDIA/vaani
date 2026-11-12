"""Metrics shared by the owner's daily brief and weekly summary (F-13).

One definition of "recovered booking" and "estimated revenue", so the two
reports can never disagree. Both follow the tenant's own configuration:
``business_hours`` decides what counts as after hours, and
``business_profile.avg_booking_value`` (INR) prices a recovered booking.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.models.collections import Bookings, Conversations

DEFAULT_AVG_BOOKING_VALUE = 1000
_MAX_AVG_BOOKING_VALUE = 1_000_000

# Legacy default used when a tenant has not configured business_hours:
# open 09:00-18:00, closed Sunday.
_DEFAULT_OPEN = time(9, 0)
_DEFAULT_CLOSE = time(18, 0)


def avg_booking_value(tenant: dict[str, Any]) -> int:
    """Owner-configured value of one booking; a safe default for bad or missing data."""
    profile = tenant.get("business_profile")
    value = profile.get("avg_booking_value") if isinstance(profile, dict) else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return DEFAULT_AVG_BOOKING_VALUE
    if not 0 < value <= _MAX_AVG_BOOKING_VALUE:
        return DEFAULT_AVG_BOOKING_VALUE
    return int(value)


def _open_hours(local: datetime, schedule: Any) -> tuple[time, time] | None:
    if not isinstance(schedule, list) or not schedule:
        if local.weekday() == 6:
            return None
        return _DEFAULT_OPEN, _DEFAULT_CLOSE
    name = local.strftime("%A").lower()
    row = next((r for r in schedule if isinstance(r, dict) and r.get("day") == name), None)
    if not row:
        return None
    try:
        return time.fromisoformat(row["start"]), time.fromisoformat(row["end"])
    except (KeyError, ValueError, TypeError):
        return None


def is_recovered(booking: dict[str, Any], tenant: dict[str, Any]) -> bool:
    """A booking Vaani recovered: made by voice, or made while the business was closed."""
    if booking.get("source") == "voice":
        return True
    created = booking.get("ts")
    if not isinstance(created, datetime):
        return False
    zone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
    local = created.replace(tzinfo=UTC).astimezone(zone)
    hours = _open_hours(local, tenant.get("business_hours"))
    return hours is None or not hours[0] <= local.time() < hours[1]


async def window_metrics(
    tenant: dict[str, Any], start_utc: datetime, end_utc: datetime
) -> dict[str, int]:
    """Counts for [start, end) given as naive-UTC datetimes (how Mongo stores them)."""
    tenant_id = str(tenant["_id"])
    conversations = await Conversations(tenant_id).count_documents(
        {"started_at": {"$gte": start_utc, "$lt": end_utc}}
    )
    bookings = [
        b
        async for b in Bookings(tenant_id).find(
            {
                "status": {"$in": ["confirmed", "completed"]},
                "ts": {"$gte": start_utc, "$lt": end_utc},
            }
        )
    ]
    recovered = sum(1 for b in bookings if is_recovered(b, tenant))
    return {
        "conversations": conversations,
        "confirmed": len(bookings),
        "recovered": recovered,
    }
