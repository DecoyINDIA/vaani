from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.agent.tools.slots_get import slots_get
from app.booking.engine import hold_slot
from app.models.base import get_db
from app.models.collections import Slots, Tenants


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


@pytest.mark.asyncio
async def test_past_slot_not_listed_and_not_holdable() -> None:
    tenant_id = "t_guard"
    now = datetime.now(UTC).replace(tzinfo=None)
    past_start = now - timedelta(hours=2)
    past_end = past_start + timedelta(minutes=30)
    today_str = now.strftime("%Y-%m-%d")

    await Tenants.find_by_id(tenant_id)
    db = get_db()
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "UTC", "booking_lead_minutes": 30})

    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_1",
            "start": past_start,
            "end": past_end,
            "status": "open",
        }
    )
    slot_id = str(slot_res.inserted_id)

    # slots_get should not return the slot
    slots = await slots_get(tenant_id, "dr_1", today_str)
    assert not any(s["slot_id"] == slot_id for s in slots)

    # hold_slot should refuse the slot
    held = await hold_slot(tenant_id, slot_id, "op_past")
    assert held is False


@pytest.mark.asyncio
async def test_slot_in_10_min_not_listed_with_default_lead_but_holdable() -> None:
    tenant_id = "t_guard"
    now = datetime.now(UTC).replace(tzinfo=None)
    start_10 = now + timedelta(minutes=10)
    end_10 = start_10 + timedelta(minutes=30)
    today_str = start_10.strftime("%Y-%m-%d")

    db = get_db()
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "UTC", "booking_lead_minutes": 30})

    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_1",
            "start": start_10,
            "end": end_10,
            "status": "open",
        }
    )
    slot_id = str(slot_res.inserted_id)

    # slots_get with 30m lead should NOT list it
    slots = await slots_get(tenant_id, "dr_1", today_str)
    assert not any(s["slot_id"] == slot_id for s in slots)

    # hold_slot allows it since start > now
    held = await hold_slot(tenant_id, slot_id, "op_10m")
    assert held is True


@pytest.mark.asyncio
async def test_slot_in_2_hours_listed_and_holdable() -> None:
    tenant_id = "t_guard"
    now = datetime.now(UTC).replace(tzinfo=None)
    start_2h = now + timedelta(hours=2)
    end_2h = start_2h + timedelta(minutes=30)
    today_str = start_2h.strftime("%Y-%m-%d")

    db = get_db()
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "UTC", "booking_lead_minutes": 30})

    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_1",
            "start": start_2h,
            "end": end_2h,
            "status": "open",
        }
    )
    slot_id = str(slot_res.inserted_id)

    # slots_get lists it
    slots = await slots_get(tenant_id, "dr_1", today_str)
    assert any(s["slot_id"] == slot_id for s in slots)

    # hold_slot succeeds
    held = await hold_slot(tenant_id, slot_id, "op_2h")
    assert held is True


@pytest.mark.asyncio
async def test_tenant_zero_lead_lists_slot_in_10_min() -> None:
    tenant_id = "t_guard"
    now = datetime.now(UTC).replace(tzinfo=None)
    start_10 = now + timedelta(minutes=10)
    end_10 = start_10 + timedelta(minutes=30)
    today_str = start_10.strftime("%Y-%m-%d")

    db = get_db()
    await db["tenants"].insert_one({"_id": tenant_id, "timezone": "UTC", "booking_lead_minutes": 0})

    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_1",
            "start": start_10,
            "end": end_10,
            "status": "open",
        }
    )
    slot_id = str(slot_res.inserted_id)

    # slots_get with 0m lead SHOULD list it
    slots = await slots_get(tenant_id, "dr_1", today_str)
    assert any(s["slot_id"] == slot_id for s in slots)
