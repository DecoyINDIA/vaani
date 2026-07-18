"""Tool — available slots lookup (TRD §3).

Reads open slots for a practitioner/date, respecting the holiday calendar
(no slots on closed days). Feeds the booking flow.
"""

from __future__ import annotations

from typing import Any


async def slots_get(tenant_id: str, practitioner_id: str, date: str) -> list[dict[str, Any]]:
    raise NotImplementedError("slots_get — 06-engineering-plan task 4.1")
