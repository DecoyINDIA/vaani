from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.agent.tools.slots_get import slots_get
from app.booking.engine import expand_schedule, run_schedule_expansion
from app.models.base import get_db


async def test_clinic_local_schedule_is_stored_utc_and_rendered_local() -> None:
    db = get_db()
    tenant_id = "t_schedule_timezone"
    practitioner_id = "p_schedule_timezone"
    await db["tenants"].insert_one(
        {"_id": tenant_id, "timezone": "Asia/Kolkata", "holiday_calendar": []}
    )
    await db["practitioners"].insert_one(
        {
            "_id": practitioner_id,
            "tenant_id": tenant_id,
            "schedule_template": {
                "monday": [{"start": "09:00", "end": "09:30"}],
            },
        }
    )
    # Sunday UTC is already Monday in India; host timezone must not affect this.
    now = datetime(2026, 12, 27, 20, 0, tzinfo=UTC)
    assert await expand_schedule(tenant_id, practitioner_id, horizon_days=1, now=now) == 1

    stored = await db["slots"].find_one({"tenant_id": tenant_id})
    assert stored["start"] == datetime(2026, 12, 28, 3, 30)
    offered = await slots_get(tenant_id, practitioner_id, "2026-12-28")
    assert offered[0]["start"] == "2026-12-28T09:00:00+05:30"


async def test_daily_expansion_is_idempotent_and_extends_past_fourteen_days() -> None:
    db = get_db()
    tenant_id = "t_schedule_rolling"
    practitioner_id = "p_schedule_rolling"
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "Asia/Kolkata"})
    await db["practitioners"].insert_one(
        {
            "_id": practitioner_id,
            "tenant_id": tenant_id,
            "schedule_template": {
                day: [{"start": "10:00", "end": "10:30"}]
                for day in (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
            },
        }
    )
    now = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
    first = await run_schedule_expansion(now=now, horizon_days=30)
    second = await run_schedule_expansion(now=now, horizon_days=30)
    assert first["slots_created"] >= 30
    assert second["slots_created"] == 0
    assert second["skipped"] >= 1

    starts = [
        slot["start"]
        async for slot in db["slots"].find({"tenant_id": tenant_id}).sort("start", 1)
    ]
    assert (starts[-1] - starts[0]).days >= 29


async def test_schedule_exhaustion_creates_pii_free_operational_alert() -> None:
    db = get_db()
    tenant_id = "t_schedule_exhausted"
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "Asia/Kolkata"})
    await db["practitioners"].insert_one(
        {
            "_id": "p_schedule_exhausted",
            "tenant_id": tenant_id,
            "schedule_template": {},
        }
    )

    stats = await run_schedule_expansion(
        now=datetime(2026, 11, 7, 0, 0, tzinfo=UTC), horizon_days=30
    )

    assert stats["alerts"] == 1
    alert = await db["audit_log"].find_one(
        {"tenant_id": tenant_id, "event_type": "operational_alert"}
    )
    assert alert["payload"] == {
        "kind": "schedule_exhaustion",
        "practitioner_id": "p_schedule_exhausted",
        "local_date": "2026-11-07",
        "horizon_days": 30,
    }


async def test_schedule_failure_is_visible_and_does_not_stop_other_tenants() -> None:
    db = get_db()
    now = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
    for tenant_id in ("t_schedule_fail", "t_schedule_continue"):
        await db["tenants"].insert_one({"_id": tenant_id, "timezone": "Asia/Kolkata"})
        await db["practitioners"].insert_one(
            {
                "_id": f"p_{tenant_id}",
                "tenant_id": tenant_id,
                "schedule_template": {"saturday": [{"start": "10:00", "end": "10:30"}]},
            }
        )

    real_expand = expand_schedule

    async def fail_one(
        tenant_id: str,
        practitioner_id: str,
        horizon_days: int = 30,
        *,
        now: datetime | None = None,
    ) -> int:
        if tenant_id == "t_schedule_fail":
            raise RuntimeError("synthetic failure")
        return await real_expand(
            tenant_id, practitioner_id, horizon_days=horizon_days, now=now
        )

    with patch("app.booking.engine.expand_schedule", side_effect=fail_one):
        stats = await run_schedule_expansion(now=now, horizon_days=7)

    assert stats["failed"] == 1
    failed_run = await db["job_runs"].find_one({"tenant_id": "t_schedule_fail"})
    assert failed_run["state"] == "failed"
    assert failed_run["error_type"] == "RuntimeError"
    assert await db["slots"].count_documents({"tenant_id": "t_schedule_continue"}) == 1
    failure_alert = await db["audit_log"].find_one(
        {
            "tenant_id": "t_schedule_fail",
            "event_type": "operational_alert",
            "payload.kind": "schedule_expansion_failed",
        }
    )
    assert failure_alert["payload"]["error_type"] == "RuntimeError"
