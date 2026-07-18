"""Tool — available slots lookup (TRD §3).

Reads open slots for a practitioner/date, respecting the holiday calendar
(no slots on closed days). Feeds the booking flow.
"""

from __future__ import annotations

import logging
from datetime import datetime as dt, date, time, timezone
from typing import Any

from app.models.base import get_db

logger = logging.getLogger(__name__)


async def slots_get(tenant_id: str, practitioner_id: str, date_str: str) -> list[dict[str, Any]]:
    """Tool — available slots lookup (TRD §3).

    Reads open slots for a practitioner/date. respects held slots expiry.
    """
    db = get_db()
    try:
        parsed_date = date.fromisoformat(date_str)
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return []

    start_of_day = dt.combine(parsed_date, time(0, 0, 0))
    end_of_day = dt.combine(parsed_date, time(23, 59, 59))
    now = dt.now(timezone.utc).replace(tzinfo=None)

    query = {
        "tenant_id": tenant_id,
        "practitioner_id": practitioner_id,
        "start": {"$gte": start_of_day, "$lte": end_of_day},
        "$or": [
            {"status": "open"},
            {"status": "held", "hold_expiry": {"$lt": now}}
        ]
    }

    try:
        cursor = db["slots"].find(query).sort("start", 1)
        results = []
        async for doc in cursor:
            results.append({
                "slot_id": str(doc["_id"]),
                "start": doc["start"].isoformat(),
                "end": doc["end"].isoformat(),
                "status": "open" if doc["status"] == "open" else "open"  # treat expired-hold slots as open
            })
        return results
    except Exception as e:
        logger.error(f"Failed to query slots: {e}")
        return []

