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


HI_WEEKDAYS: dict[int, str] = {
    0: "सोम",
    1: "मंगल",
    2: "बुध",
    3: "गुरु",
    4: "शुक्र",
    5: "शनि",
    6: "रवि",
}

HI_MONTHS: dict[int, str] = {
    1: "जन",
    2: "फ़र",
    3: "मार्च",
    4: "अप्रैल",
    5: "मई",
    6: "जून",
    7: "जुल",
    8: "अग",
    9: "सित",
    10: "अक्टू",
    11: "नव",
    12: "दिस",
}

OR_WEEKDAYS: dict[int, str] = {
    0: "ସୋମ",
    1: "ମଙ୍ଗଳ",
    2: "ବୁଧ",
    3: "ଗୁରୁ",
    4: "ଶୁକ୍ର",
    5: "ଶନି",
    6: "ରବି",
}


def format_local(instant: datetime, tz: ZoneInfo, lang: str = "en") -> str:
    """Naive datetimes are treated as UTC. Returns formatted string e.g. 'Thu 12 Nov, 10:00 AM'."""
    if instant.tzinfo is None:
        aware = instant.replace(tzinfo=UTC).astimezone(tz)
    else:
        aware = instant.astimezone(tz)

    time_str = aware.strftime("%I:%M %p")
    day_num = aware.day

    if lang == "hi":
        weekday = HI_WEEKDAYS[aware.weekday()]
        month = HI_MONTHS[aware.month]
        return f"{weekday} {day_num:02d} {month}, {time_str}"
    elif lang == "or":
        weekday = OR_WEEKDAYS[aware.weekday()]
        month_num = aware.month
        return f"{weekday} {day_num:02d}/{month_num:02d}, {time_str}"
    else:
        # "en" and "hi-Latn"
        return aware.strftime("%a %d %b, %I:%M %p")
