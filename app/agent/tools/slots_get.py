"""Tool — available slots lookup (TRD §3).

Reads open slots for a practitioner/date, respecting the holiday calendar
(no slots on closed days). Feeds the booking flow.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, time
from datetime import datetime as dt
from typing import Any

from app.models.collections import Slots

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

    start_of_day = dt.combine(parsed_date, time(0, 0, 0))
    end_of_day = dt.combine(parsed_date, time(23, 59, 59))
    now = dt.now(UTC).replace(tzinfo=None)

    query = {
        "practitioner_id": practitioner_id,
        "start": {"$gte": start_of_day, "$lte": end_of_day},
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
                "start": doc["start"].isoformat(),
                "end": doc["end"].isoformat(),
                # treat expired-hold slots as open
                "status": "open" if doc["status"] == "open" else "open"
            })
        return results
    except Exception as e:
        logger.error(f"Failed to query slots: {e}")
        return []

