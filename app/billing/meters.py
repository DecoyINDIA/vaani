"""Usage metering + daily per-tenant cost report (TRD §6, Week 5 task 5.5).

Meters LLM tokens, Meta billable messages, voice minutes; rolls up to
usage_meters. Daily cost report lands on the owner's WhatsApp — a LAUNCH BLOCKER,
not an afterthought (cost visibility per TRD §6).
"""

from __future__ import annotations


async def record_usage(tenant_id: str, **counters: int) -> None:
    raise NotImplementedError("usage metering — 06-engineering-plan task 5.5")
