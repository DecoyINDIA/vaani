from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Kolkata"


def tenant_timezone(tenant: dict[str, Any] | None) -> ZoneInfo:
    """ZoneInfo(tenant['timezone']) or Asia/Kolkata when missing/invalid."""
    if tenant and isinstance(tenant.get("timezone"), str):
        try:
            return ZoneInfo(tenant["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo(DEFAULT_TIMEZONE)


def format_local(instant: datetime, tz: ZoneInfo) -> str:
    """Naive datetimes are treated as UTC. Returns e.g. 'Thu 12 Nov, 10:00 AM'."""
    if instant.tzinfo is None:
        aware = instant.replace(tzinfo=UTC).astimezone(tz)
    else:
        aware = instant.astimezone(tz)
    return aware.strftime("%a %d %b, %I:%M %p")
