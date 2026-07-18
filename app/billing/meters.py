"""Usage metering + daily per-tenant cost report (TRD §6, Week 5 task 5.5).

Meters LLM tokens, Meta billable messages, voice minutes; rolls up to
usage_meters. Daily cost report lands on the owner's WhatsApp — a LAUNCH BLOCKER,
not an afterthought (cost visibility per TRD §6).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.collections import UsageMeters


async def record_usage(tenant_id: str, **counters: int) -> None:
    """Increment usage counters for the tenant in the current period (YYYY-MM)."""
    period = datetime.now(UTC).strftime("%Y-%m")

    update_fields = {}
    for key, val in counters.items():
        update_fields[key] = val

    if not update_fields:
        return

    accessor = UsageMeters(tenant_id)
    await accessor.find_one_and_update(
        {"period": period},
        {"$inc": update_fields},
        upsert=True
    )
