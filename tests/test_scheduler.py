from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.booking import engine
from app.config import settings
from app.gateway.middleware import get_redis
from app.models.base import get_db
from app.models.collections import JobRuns, Practitioners
from app.workers import healthcheck, inbound, scheduler


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


async def test_run_once_calls_all_steps_in_order() -> None:
    call_order: list[str] = []

    async def mock_stale():
        call_order.append("stale_sends")
        return 0

    async def mock_expansion(*, now=None):
        call_order.append("slot_expansion")
        return {}

    async def mock_reminders(*, now=None):
        call_order.append("reminders")

    async def mock_escalations(*, now=None):
        call_order.append("escalation_slas")

    async def mock_invoices(*, now=None):
        call_order.append("monthly_invoices")

    async def mock_daily(*, now=None):
        call_order.append("daily_briefs")

    async def mock_weekly(*, now=None):
        call_order.append("weekly_summaries")

    with patch.object(settings, "enable_billing", True):
        with (
            patch("app.models.collections.OutboundIntents.mark_stale_sending_unknown_unscoped", side_effect=mock_stale),
            patch("app.workers.scheduler.run_schedule_expansion", side_effect=mock_expansion),
            patch("app.workers.scheduler.run_reminders", side_effect=mock_reminders),
            patch("app.workers.scheduler.run_escalation_slas", side_effect=mock_escalations),
            patch("app.workers.scheduler.run_monthly_invoices", side_effect=mock_invoices),
            patch("app.workers.scheduler.run_daily_briefs", side_effect=mock_daily),
            patch("app.workers.scheduler.run_weekly_summaries", side_effect=mock_weekly),
        ):
            results = await scheduler.run_once()

    expected_order = [
        "stale_sends",
        "slot_expansion",
        "reminders",
        "escalation_slas",
        "monthly_invoices",
        "daily_briefs",
        "weekly_summaries",
    ]
    assert call_order == expected_order
    for k in expected_order:
        assert results[k] == "ok"


async def test_run_once_step_failure_is_isolated() -> None:
    async def mock_failing_reminders(*, now=None):
        raise RuntimeError("network failure in reminders")

    with (
        patch("app.models.collections.OutboundIntents.mark_stale_sending_unknown_unscoped", AsyncMock(return_value=0)),
        patch("app.workers.scheduler.run_schedule_expansion", AsyncMock(return_value={})),
        patch("app.workers.scheduler.run_reminders", side_effect=mock_failing_reminders),
        patch("app.workers.scheduler.run_escalation_slas", AsyncMock()),
        patch("app.workers.scheduler.run_daily_briefs", AsyncMock()),
        patch("app.workers.scheduler.run_weekly_summaries", AsyncMock()),
    ):
        with patch.object(settings, "enable_billing", False):
            results = await scheduler.run_once()

    assert results["stale_sends"] == "ok"
    assert results["slot_expansion"] == "ok"
    assert results["reminders"] == "error"
    assert results["escalation_slas"] == "ok"
    assert results["monthly_invoices"] == "skipped"
    assert results["daily_briefs"] == "ok"
    assert results["weekly_summaries"] == "ok"


async def test_run_once_invoices_skipped_when_billing_disabled() -> None:
    with (
        patch("app.models.collections.OutboundIntents.mark_stale_sending_unknown_unscoped", AsyncMock(return_value=0)),
        patch("app.workers.scheduler.run_schedule_expansion", AsyncMock(return_value={})),
        patch("app.workers.scheduler.run_reminders", AsyncMock()),
        patch("app.workers.scheduler.run_escalation_slas", AsyncMock()),
        patch("app.workers.scheduler.run_monthly_invoices", AsyncMock()) as invoice_mock,
        patch("app.workers.scheduler.run_daily_briefs", AsyncMock()),
        patch("app.workers.scheduler.run_weekly_summaries", AsyncMock()),
    ):
        with patch.object(settings, "enable_billing", False):
            results = await scheduler.run_once()

    invoice_mock.assert_not_called()
    assert results["monthly_invoices"] == "skipped"


async def test_run_schedule_expansion_retries_failed_row() -> None:
    tenant_id = "t_retry"
    await get_db()["tenants"].insert_one({"_id": tenant_id, "name": "Retry Clinic", "timezone": "Asia/Kolkata"})
    await Practitioners(tenant_id).insert_one(
        {
            "_id": "p_1",
            "name": "Dr. Test",
            "schedule_template": {
                "monday": [{"start": "09:00", "end": "10:00"}],
                "tuesday": [{"start": "09:00", "end": "10:00"}],
                "wednesday": [{"start": "09:00", "end": "10:00"}],
                "thursday": [{"start": "09:00", "end": "10:00"}],
                "friday": [{"start": "09:00", "end": "10:00"}],
                "saturday": [{"start": "09:00", "end": "10:00"}],
                "sunday": [{"start": "09:00", "end": "10:00"}],
            },
        }
    )

    now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)
    local_date = "2026-11-12"
    job_id = f"slot-expansion:{tenant_id}:{local_date}"

    # Insert a failed job run
    await JobRuns(tenant_id).insert_one(
        {
            "_id": job_id,
            "job": "slot_expansion",
            "key": local_date,
            "state": "failed",
            "started_at": now.replace(tzinfo=None) - timedelta(minutes=10),
            "error_type": "SimulatedError",
        }
    )

    stats = await engine.run_schedule_expansion(now=now, horizon_days=3)
    assert stats["skipped"] == 0
    assert stats["tenants"] == 1
    assert stats["slots_created"] > 0

    job = await JobRuns(tenant_id).find_one({"_id": job_id})
    assert job is not None
    assert job["state"] == "completed"
    assert job.get("retries", 0) >= 1


async def test_run_schedule_expansion_retries_stale_running_row() -> None:
    tenant_id = "t_stale"
    await get_db()["tenants"].insert_one({"_id": tenant_id, "name": "Stale Clinic", "timezone": "Asia/Kolkata"})
    await Practitioners(tenant_id).insert_one(
        {
            "_id": "p_stale",
            "name": "Dr. Stale",
            "schedule_template": {
                "monday": [{"start": "09:00", "end": "10:00"}],
                "tuesday": [{"start": "09:00", "end": "10:00"}],
                "wednesday": [{"start": "09:00", "end": "10:00"}],
                "thursday": [{"start": "09:00", "end": "10:00"}],
                "friday": [{"start": "09:00", "end": "10:00"}],
                "saturday": [{"start": "09:00", "end": "10:00"}],
                "sunday": [{"start": "09:00", "end": "10:00"}],
            },
        }
    )

    now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)
    local_date = "2026-11-12"
    job_id = f"slot-expansion:{tenant_id}:{local_date}"

    # Insert running job older than 30 minutes
    await JobRuns(tenant_id).insert_one(
        {
            "_id": job_id,
            "job": "slot_expansion",
            "key": local_date,
            "state": "running",
            "started_at": now.replace(tzinfo=None) - timedelta(minutes=45),
        }
    )

    stats = await engine.run_schedule_expansion(now=now, horizon_days=3)
    assert stats["skipped"] == 0
    assert stats["tenants"] == 1

    job = await JobRuns(tenant_id).find_one({"_id": job_id})
    assert job is not None
    assert job["state"] == "completed"
    assert job.get("retries", 0) >= 1


async def test_run_schedule_expansion_skips_fresh_running_and_completed_row() -> None:
    tenant_id = "t_skip"
    await get_db()["tenants"].insert_one({"_id": tenant_id, "name": "Skip Clinic", "timezone": "Asia/Kolkata"})

    now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)
    local_date = "2026-11-12"
    job_id = f"slot-expansion:{tenant_id}:{local_date}"

    # 1. Fresh running row (started 5 minutes ago)
    await JobRuns(tenant_id).insert_one(
        {
            "_id": job_id,
            "job": "slot_expansion",
            "key": local_date,
            "state": "running",
            "started_at": now.replace(tzinfo=None) - timedelta(minutes=5),
        }
    )

    stats = await engine.run_schedule_expansion(now=now, horizon_days=3)
    assert stats["skipped"] == 1
    assert stats["tenants"] == 0

    # 2. Completed row
    await JobRuns(tenant_id).update_one({"_id": job_id}, {"$set": {"state": "completed"}})
    stats2 = await engine.run_schedule_expansion(now=now, horizon_days=3)
    assert stats2["skipped"] == 1
    assert stats2["tenants"] == 0


async def test_inbound_run_does_not_invoke_scheduled_jobs() -> None:
    with (
        patch("app.workers.scheduler.run_schedule_expansion", AsyncMock()) as expansion_mock,
        patch("app.workers.scheduler.run_reminders", AsyncMock()) as reminder_mock,
        patch.object(inbound, "_ensure_group", AsyncMock()),
    ):
        redis = get_redis()
        redis.set = AsyncMock()
        redis.xautoclaim = AsyncMock(return_value=(None, [], None))
        redis.xreadgroup = AsyncMock(return_value=[])

        # Run 1 iteration of inbound worker
        await inbound.run(iterations=1)

    expansion_mock.assert_not_called()
    reminder_mock.assert_not_called()


async def test_healthcheck_custom_key_and_max_age() -> None:
    custom_key = "vaani:scheduler:heartbeat"
    mock_redis = AsyncMock()

    # 1. Healthy heartbeat
    now_ts = datetime.now(UTC).timestamp()
    mock_redis.get = AsyncMock(return_value=str(now_ts))
    with patch("app.workers.healthcheck.get_redis", return_value=mock_redis):
        await healthcheck.check(key=custom_key, max_age_seconds=120.0)

    # 2. Stale heartbeat raises SystemExit and logs audit with component
    stale_ts = now_ts - 500
    mock_redis.get = AsyncMock(return_value=str(stale_ts))
    with patch("app.workers.healthcheck.get_redis", return_value=mock_redis):
        with pytest.raises(SystemExit) as exc_info:
            await healthcheck.check(key=custom_key, max_age_seconds=120.0)
        assert "heartbeat is stale" in str(exc_info.value)

    # Verify audit record contains component
    audit_doc = await get_db()["audit_log"].find_one(
        {"event_type": "operational_alert", "payload.component": custom_key}
    )
    assert audit_doc is not None
    assert audit_doc["payload"]["kind"] == "worker_heartbeat"
