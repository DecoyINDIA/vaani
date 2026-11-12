"""Owner daily brief (F-13): content, schedule, idempotency, and per-tenant configuration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.channels.whatsapp import TEMPLATE_CONTRACTS, TEMPLATE_PACK
from app.models.base import get_db
from app.reporting import DEFAULT_AVG_BOOKING_VALUE, avg_booking_value
from app.workers.daily_brief import run_daily_briefs

# 08:00 IST on Tuesday 10 Nov 2026 -> the brief covers Monday 9 Nov, local day.
SEND_TIME = datetime(2026, 11, 10, 2, 30, tzinfo=UTC)
MON_START = datetime(2026, 11, 8, 18, 30)  # Monday 00:00 IST as naive UTC


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute)


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


async def _tenant(tenant_id: str, **extra: Any) -> None:
    db = get_db()
    await db["tenants"].insert_one(
        {"_id": tenant_id, "name": "Glow Salon", "timezone": "Asia/Kolkata", "status": "active", **extra}
    )
    await db["users"].insert_one(
        {"tenant_id": tenant_id, "role": "owner", "status": "active", "wa_id": "919999999991"}
    )


async def _booking(tenant_id: str, ts: datetime, *, status: str = "confirmed", source: str = "wa") -> None:
    await get_db()["bookings"].insert_one(
        {"tenant_id": tenant_id, "status": status, "source": source, "ts": ts}
    )


async def _sent(tenant_id: str) -> list[dict[str, Any]]:
    return [
        doc
        async for doc in get_db()["audit_log"].find(
            {"tenant_id": tenant_id, "payload.template": "daily_brief_owner"}
        )
    ]


async def test_brief_reports_yesterday_for_the_tenant_only_and_is_idempotent() -> None:
    tid = "salon_a"
    db = get_db()
    await _tenant(tid, business_profile={"avg_booking_value": 1500})
    await _tenant("other_tenant")

    for hour in (4, 5):  # two conversations on Monday
        await db["conversations"].insert_one(
            {"tenant_id": tid, "state": "bot", "started_at": _utc(9, hour)}
        )
    await db["conversations"].insert_one(  # Sunday: outside the window
        {"tenant_id": tid, "state": "bot", "started_at": _utc(8, 10)}
    )
    await db["conversations"].insert_one(  # another tenant's Monday traffic
        {"tenant_id": "other_tenant", "state": "bot", "started_at": _utc(9, 5)}
    )

    await _booking(tid, _utc(9, 6, 30))  # Mon 12:00 IST, in hours
    await _booking(tid, _utc(9, 14, 30))  # Mon 20:00 IST, after hours -> recovered
    await _booking(tid, _utc(9, 4, 30), source="voice")  # voice -> recovered
    await _booking(tid, _utc(9, 7), status="cancelled")  # not counted
    await _booking(tid, _utc(10, 1))  # Tuesday: outside the window
    await db["escalations"].insert_one({"tenant_id": tid, "status": "open"})
    await db["escalations"].insert_one({"tenant_id": tid, "status": "resolved"})

    await run_daily_briefs(now=SEND_TIME)
    await run_daily_briefs(now=SEND_TIME)

    sent = await _sent(tid)
    assert len(sent) == 1
    assert sent[0]["operation_key"] == f"daily-brief:{tid}:2026-11-09"
    assert sent[0]["payload"]["variables"] == {
        "owner_name": "Glow Salon",
        "date_str": "Mon, 09 Nov",
        "convs_count": "2",
        "confirmed_count": "3",
        "recovered_count": "2",
        "revenue_str": "Rs. 3000",
        "open_escalations": "1",
    }
    other = (await _sent("other_tenant"))[0]["payload"]["variables"]
    assert other["convs_count"] == "1"


async def test_brief_only_goes_out_in_the_owners_eight_oclock_hour() -> None:
    await _tenant("salon_b")
    await run_daily_briefs(now=datetime(2026, 11, 10, 3, 30, tzinfo=UTC))  # 09:00 IST
    await run_daily_briefs(now=datetime(2026, 11, 10, 2, 0, tzinfo=UTC))  # 07:30 IST
    assert await _sent("salon_b") == []
    await run_daily_briefs(now=datetime(2026, 11, 10, 2, 45, tzinfo=UTC))  # 08:15 IST
    assert len(await _sent("salon_b")) == 1


async def test_yesterday_includes_start_midnight_and_excludes_today_midnight() -> None:
    await _tenant("midnight")
    today_start = MON_START + timedelta(days=1)
    for instant in (MON_START - timedelta(milliseconds=1), MON_START, today_start):
        await get_db()["conversations"].insert_one(
            {"tenant_id": "midnight", "started_at": instant}
        )
        await _booking("midnight", instant, source="voice")

    await run_daily_briefs(now=SEND_TIME)

    variables = (await _sent("midnight"))[0]["payload"]["variables"]
    assert variables["convs_count"] == "1"
    assert variables["confirmed_count"] == "1"
    assert variables["recovered_count"] == "1"


async def test_local_day_spans_dst_change_and_uses_tenant_send_hour() -> None:
    await _tenant("new_york", timezone="America/New_York")
    # Nov 1 is 25 hours long: midnight EDT to midnight EST.
    for instant in (
        _utc(1, 3, 59),  # previous day
        _utc(1, 4),
        _utc(2, 4, 59),
        _utc(2, 5),  # next day
    ):
        await _booking("new_york", instant, source="voice")

    await run_daily_briefs(now=datetime(2026, 11, 2, 12, tzinfo=UTC))  # 07:00 EST
    assert await _sent("new_york") == []
    await run_daily_briefs(now=datetime(2026, 11, 2, 13, tzinfo=UTC))  # 08:00 EST
    sent = (await _sent("new_york"))[0]
    assert sent["operation_key"] == "daily-brief:new_york:2026-11-01"
    assert sent["payload"]["variables"]["confirmed_count"] == "2"


async def test_brief_rejects_naive_clock() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await run_daily_briefs(now=SEND_TIME.replace(tzinfo=None))


async def test_brief_builds_english_template_payload_without_an_open_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.channels import whatsapp

    await _tenant("payload")
    # No contact or inbound window: inspect the outbound template boundary offline.
    captured: list[dict[str, Any]] = []

    async def capture(
        tenant_id: str, wa_id: str, body: dict[str, Any], operation_key: str
    ) -> dict[str, Any]:
        captured.append(body)
        assert tenant_id == "payload"
        assert wa_id == "919999999991"
        assert operation_key == "daily-brief:payload:2026-11-09"
        return {"messages": [{"id": "synthetic-daily-brief"}]}

    monkeypatch.setattr(whatsapp, "_post", capture)
    await run_daily_briefs(now=SEND_TIME)
    assert len(captured) == 1
    assert captured[0]["type"] == "template"
    assert captured[0]["template"] == {
        "name": "daily_brief_owner",
        "language": {"code": "en"},
        "components": [{"type": "body", "parameters": [
            {"type": "text", "text": value}
            for value in ("Glow Salon", "Mon, 09 Nov", "0", "0", "0", "Rs. 0", "0")
        ]}],
    }


async def test_tenant_can_opt_out_and_inactive_tenants_are_skipped() -> None:
    await _tenant("opted_out", daily_brief_enabled=False)
    await _tenant("suspended", status="suspended")
    await run_daily_briefs(now=SEND_TIME)
    assert await _sent("opted_out") == []
    assert await _sent("suspended") == []


async def test_after_hours_follows_the_tenants_own_business_hours() -> None:
    late = _utc(9, 13, 30)  # Mon 19:00 IST
    await _tenant("default_hours")
    await _tenant(
        "late_salon", business_hours=[{"day": "monday", "start": "10:00", "end": "20:00"}]
    )
    await _booking("default_hours", late)
    await _booking("late_salon", late)

    await run_daily_briefs(now=SEND_TIME)

    default = (await _sent("default_hours"))[0]["payload"]["variables"]
    late_salon = (await _sent("late_salon"))[0]["payload"]["variables"]
    assert default["recovered_count"] == "1"  # 19:00 is after the 09-18 default
    assert late_salon["recovered_count"] == "0"  # open until 20:00


async def test_missing_owner_is_visible_without_a_false_send() -> None:
    db = get_db()
    await db["tenants"].insert_one(
        {"_id": "no_owner", "name": "No Owner", "timezone": "Asia/Kolkata", "status": "active"}
    )
    await run_daily_briefs(now=SEND_TIME)
    await run_daily_briefs(now=SEND_TIME)
    assert await _sent("no_owner") == []
    alerts = [a async for a in db["audit_log"].find({"tenant_id": "no_owner", "event_type": "operational_alert"})]
    assert [a["payload"] for a in alerts] == [{"kind": "daily_brief_missing_recipient", "day": "2026-11-09"}]


async def test_one_tenants_failure_does_not_stop_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    await _tenant("broken")
    await _tenant("healthy")
    from app.workers import daily_brief

    real = daily_brief.window_metrics

    async def flaky(tenant: dict[str, Any], start: datetime, end: datetime) -> dict[str, int]:
        if tenant["_id"] == "broken":
            raise RuntimeError("boom")
        return await real(tenant, start, end)

    monkeypatch.setattr(daily_brief, "window_metrics", flaky)
    await run_daily_briefs(now=SEND_TIME)

    assert len(await _sent("healthy")) == 1
    alert = await get_db()["audit_log"].find_one({"tenant_id": "broken", "event_type": "operational_alert"})
    assert alert["payload"]["kind"] == "daily_brief_failed"
    assert alert["payload"]["error_type"] == "RuntimeError"


@pytest.mark.parametrize("bad", [None, "1500", True, 0, -5, 10**9, float("nan")])
def test_bad_booking_value_falls_back_to_the_default(bad: object) -> None:
    assert avg_booking_value({"business_profile": {"avg_booking_value": bad}}) == DEFAULT_AVG_BOOKING_VALUE
    assert avg_booking_value({}) == DEFAULT_AVG_BOOKING_VALUE
    assert avg_booking_value({"business_profile": "nope"}) == DEFAULT_AVG_BOOKING_VALUE


def test_daily_brief_template_is_registered_with_a_stable_positional_contract() -> None:
    assert "daily_brief_owner" in TEMPLATE_PACK
    assert TEMPLATE_CONTRACTS["daily_brief_owner"] == (
        "owner_name",
        "date_str",
        "convs_count",
        "confirmed_count",
        "recovered_count",
        "revenue_str",
        "open_escalations",
    )
