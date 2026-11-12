"""Dedicated background scheduler worker (W2-07).

Runs periodic maintenance jobs independently of the inbound message worker:
- stale-send reconciliation
- slot schedule expansion
- appointment reminders
- escalation SLAs
- monthly invoicing (when enabled)
- daily briefs
- weekly summaries

Entrypoint: `python -m app.workers.scheduler`
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app import audit
from app.booking.engine import run_schedule_expansion
from app.config import settings
from app.gateway.middleware import get_redis
from app.models.collections import OutboundIntents
from app.workers.billing import run_monthly_invoices
from app.workers.daily_brief import run_daily_briefs
from app.workers.escalations import run_escalation_slas
from app.workers.reminders import run_reminders
from app.workers.weekly_summary import run_weekly_summaries

logger = logging.getLogger(__name__)

HEARTBEAT_KEY = "vaani:scheduler:heartbeat"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def run_once(*, now: datetime | None = None) -> dict[str, str]:
    """Execute each periodic maintenance job once in order.

    Returns a status mapping: {job_name: "ok" | "error" | "skipped"}.
    Each step is isolated with try/except so one failure does not halt remaining jobs.
    """
    results: dict[str, str] = {}

    # 1. Stale-send reconciliation
    try:
        reconciled = await OutboundIntents.mark_stale_sending_unknown_unscoped()
        if reconciled:
            logger.warning("Marked %d interrupted outbound sends unknown", reconciled)
            await audit.record(
                "system",
                actor="system",
                event_type="operational_alert",
                payload={"kind": "unknown_delivery", "reconciled_count": reconciled},
            )
        results["stale_sends"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in send reconciliation: %s", e, exc_info=True)
        results["stale_sends"] = "error"

    # 2. Slot schedule expansion
    try:
        await run_schedule_expansion(now=now)
        results["slot_expansion"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in slot expansion: %s", e, exc_info=True)
        results["slot_expansion"] = "error"

    # 3. Reminders
    try:
        logger.info("Scheduler: running reminders scan...")
        await run_reminders(now=now)
        results["reminders"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in reminders: %s", e, exc_info=True)
        results["reminders"] = "error"

    # 4. Escalation SLAs
    try:
        await run_escalation_slas(now=now)
        results["escalation_slas"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in escalation SLAs: %s", e, exc_info=True)
        results["escalation_slas"] = "error"

    # 5. Monthly invoices (F-17 / W1-08)
    if settings.enable_billing:
        try:
            await run_monthly_invoices(now=now)
            results["monthly_invoices"] = "ok"
        except Exception as e:
            logger.error("Scheduler error in billing: %s", e, exc_info=True)
            results["monthly_invoices"] = "error"
    else:
        results["monthly_invoices"] = "skipped"

    # 6. Daily briefs
    try:
        await run_daily_briefs(now=now)
        results["daily_briefs"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in daily briefs: %s", e, exc_info=True)
        results["daily_briefs"] = "error"

    # 7. Weekly summaries
    try:
        await run_weekly_summaries(now=now)
        results["weekly_summaries"] = "ok"
    except Exception as e:
        logger.error("Scheduler error in weekly summaries: %s", e, exc_info=True)
        results["weekly_summaries"] = "error"

    return results


async def run_scheduler_background() -> None:
    """Run scheduled background maintenance jobs indefinitely."""
    logger.info("Starting background scheduler...")
    r: Any = get_redis()
    interval = settings.scheduler_interval_seconds
    heartbeat_ttl = max(60, interval * 3)

    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error("Unhandled error in scheduler run_once: %s", e, exc_info=True)

        try:
            await r.set(HEARTBEAT_KEY, str(_now().timestamp()), ex=heartbeat_ttl)
        except Exception as e:
            logger.warning("Failed to record scheduler heartbeat: %s", e)

        await asyncio.sleep(interval)


def main() -> None:
    from app.observability import init_observability

    settings.validate_runtime()
    init_observability("scheduler")
    logger.info("Starting scheduler worker process...")
    asyncio.run(run_scheduler_background())


if __name__ == "__main__":
    main()
