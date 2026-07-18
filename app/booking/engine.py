"""Slot engine (TRD §3, Week 4 task 4.1/4.2).

Schedule expansion: practitioner schedule_template -> concrete `slots` rows via a
nightly job. The holiday calendar blocks generation on closed days (Odisha
festival set seeded at onboarding; owner-editable). Atomic hold/confirm lives with
the booking tools; this module owns generation + closure logic.
"""

from __future__ import annotations


async def expand_schedule(tenant_id: str, practitioner_id: str, horizon_days: int = 30) -> int:
    """Generate open slots for the horizon, skipping holiday_calendar closures."""
    raise NotImplementedError("schedule expansion — 06-engineering-plan task 4.1")
