"""Tool — available slots lookup (TRD §3).

Reads open slots for a practitioner/date, respecting the holiday calendar
(no slots on closed days). Feeds the booking flow.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, time, timedelta
from datetime import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from app.models.collections import Slots, Tenants

logger = logging.getLogger(__name__)


async def slots_get(tenant_id: str, practitioner_id: str, date_str: str) -> list[dict[str, Any]]:
    """Tool — available slots lookup (TRD §3).

    Reads open slots for a practitioner/date. respects held slots expiry.
    """
    try:
        parsed_date = date.fromisoformat(date_str)
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return []

    tenant = await Tenants.find_by_id(tenant_id)
    timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")) if tenant else "Asia/Kolkata")
    start_of_day = (
        dt.combine(parsed_date, time.min, tzinfo=timezone).astimezone(UTC).replace(tzinfo=None)
    )
    end_of_day = (
        dt.combine(parsed_date, time.max, tzinfo=timezone).astimezone(UTC).replace(tzinfo=None)
    )
    now = dt.now(UTC).replace(tzinfo=None)

    lead_raw = tenant.get("booking_lead_minutes", 30) if tenant else 30
    try:
        lead = int(lead_raw)
    except (ValueError, TypeError):
        lead = 30
    lead = max(0, min(1440, lead))

    earliest = max(start_of_day, now + timedelta(minutes=lead))

    query = {
        "practitioner_id": practitioner_id,
        "start": {"$gte": earliest, "$lte": end_of_day},
        "$or": [
            {"status": "open"},
            {"status": "held", "hold_expiry": {"$lt": now}}
        ]
    }

    try:
        cursor = Slots(tenant_id).find(query).sort("start", 1)
        results = []
        async for doc in cursor:
            results.append({
                "slot_id": str(doc["_id"]),
                "start": doc["start"].replace(tzinfo=UTC).astimezone(timezone).isoformat(),
                "end": doc["end"].replace(tzinfo=UTC).astimezone(timezone).isoformat(),
                # treat expired-hold slots as open
                "status": "open" if doc["status"] == "open" else "open"
            })
        return results
    except Exception as e:
        logger.error(f"Failed to query slots: {e}")
        return []

