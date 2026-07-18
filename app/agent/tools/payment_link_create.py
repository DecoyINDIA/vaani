"""Tool — Razorpay payment link (TRD §3, TRD §5) — Phase 3.

Creates a payment link, records a payments row, reconciled by the razorpay
webhook. Opt-in gated; max-2 nudge sequence (06-engineering-plan Phase 3 item 4).
"""

from __future__ import annotations

from typing import Any


async def payment_link_create(
    tenant_id: str, contact_id: str, amount: int, *, booking_id: str | None = None
) -> dict[str, Any]:
    raise NotImplementedError("payment_link_create — 06-engineering-plan Phase 3")
