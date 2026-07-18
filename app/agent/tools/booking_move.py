"""Tool — reschedule booking (TRD §3). Same atomic hold semantics + date_confirmed
contract as booking_create."""

from __future__ import annotations

from typing import Any


async def booking_move(
    tenant_id: str, booking_id: str, new_slot_id: str, *, date_confirmed: bool
) -> dict[str, Any]:
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before move (TRD §4.3)")
    raise NotImplementedError("booking_move — 06-engineering-plan task 4.2")
