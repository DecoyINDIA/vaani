from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.booking.timefmt import format_local, tenant_timezone


def test_format_local_morning_ist() -> None:
    dt = datetime(2026, 11, 12, 4, 30)
    assert format_local(dt, ZoneInfo("Asia/Kolkata")) == "Thu 12 Nov, 10:00 AM"


def test_format_local_date_rollover_ist() -> None:
    dt = datetime(2026, 11, 12, 18, 45)
    assert format_local(dt, ZoneInfo("Asia/Kolkata")) == "Fri 13 Nov, 12:15 AM"


def test_format_local_timezone_aware() -> None:
    dt = datetime(2026, 11, 12, 4, 30, tzinfo=UTC)
    assert format_local(dt, ZoneInfo("Asia/Kolkata")) == "Thu 12 Nov, 10:00 AM"


def test_tenant_timezone_default_when_none_or_missing() -> None:
    assert tenant_timezone(None) == ZoneInfo("Asia/Kolkata")
    assert tenant_timezone({}) == ZoneInfo("Asia/Kolkata")
    assert tenant_timezone({"timezone": None}) == ZoneInfo("Asia/Kolkata")


def test_tenant_timezone_invalid_falls_back() -> None:
    assert tenant_timezone({"timezone": "Invalid/Unknown_Zone"}) == ZoneInfo("Asia/Kolkata")
    assert tenant_timezone({"timezone": ""}) == ZoneInfo("Asia/Kolkata")


def test_tenant_timezone_valid() -> None:
    assert tenant_timezone({"timezone": "UTC"}) == ZoneInfo("UTC")
    assert tenant_timezone({"timezone": "America/New_York"}) == ZoneInfo("America/New_York")
