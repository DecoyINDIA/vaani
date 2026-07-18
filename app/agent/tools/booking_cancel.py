"""Tool — cancel booking (TRD §3). Frees the slot (status -> open)."""

from __future__ import annotations

from typing import Any


async def booking_cancel(tenant_id: str, booking_id: str) -> dict[str, Any]:
    raise NotImplementedError("booking_cancel — 06-engineering-plan task 4.2")
