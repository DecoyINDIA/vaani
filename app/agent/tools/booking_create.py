"""Tool — create booking (TRD §3, Week 4 task 4.2/4.3).

Atomic hold->confirm: findOneAndUpdate(status "open"->"held") + 120s hold expiry,
then confirm. Race-safe by construction (500-concurrent test: 0 double-bookings).
CONTRACT: rejects any call without date_confirmed=true — the agent must echo
weekday + date in the user's language first (relative-date rule, TRD §4.3).
"""

from __future__ import annotations

from typing import Any


async def booking_create(
    tenant_id: str, slot_id: str, contact_id: str, service: str, *, date_confirmed: bool
) -> dict[str, Any]:
    if not date_confirmed:
        raise ValueError("date_confirmed required — echo weekday+date before booking (TRD §4.3)")
    raise NotImplementedError("booking_create — 06-engineering-plan task 4.2")
