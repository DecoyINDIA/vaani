"""Real MongoDB replica-set evidence for booking transactions and races."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest
from app.booking.engine import create_booking
from app.config import settings
from app.models import base
from app.models.collections import Bookings, Slots, ensure_indexes
from motor.motor_asyncio import AsyncIOMotorClient

URI = os.getenv("VAANI_INTEGRATION_MONGODB_URI")
pytestmark = pytest.mark.skipif(not URI, reason="real replica-set MongoDB URI not configured")


@pytest.fixture(autouse=True)
async def real_database() -> None:
    assert URI is not None
    client = AsyncIOMotorClient(URI)
    old_client = base._client
    old_mock = settings.use_mock_adapters
    base._client = client
    settings.use_mock_adapters = False
    db = base.get_db()
    await db.client.admin.command("ping")
    await ensure_indexes()
    for collection in ("slots", "bookings"):
        await db[collection].delete_many({"tenant_id": {"$regex": "^integration-"}})
    try:
        yield
    finally:
        for collection in ("slots", "bookings"):
            await db[collection].delete_many({"tenant_id": {"$regex": "^integration-"}})
        client.close()
        base._client = old_client
        settings.use_mock_adapters = old_mock


async def test_500_claims_create_one_booking_and_no_orphan_slot() -> None:
    tenant_id = "integration-race"
    await Slots(tenant_id).insert_one({"_id": "race-slot", "status": "open"})

    results = await asyncio.gather(
        *(
            create_booking(
                tenant_id,
                "race-slot",
                f"contact-{index}",
                "Cleaning",
                f"request-{index}",
            )
            for index in range(500)
        )
    )

    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert await Bookings(tenant_id).count_documents({}) == 1
    slot = await Slots(tenant_id).find_one({"_id": "race-slot"})
    booking = await Bookings(tenant_id).find_one({})
    assert slot is not None and booking is not None
    assert slot["status"] == "booked"
    assert slot["booking_id"] == booking["_id"]


async def test_insert_failure_rolls_back_slot_transaction() -> None:
    tenant_id = "integration-rollback"
    await Slots(tenant_id).insert_one({"_id": "rollback-slot", "status": "open"})

    with patch.object(Bookings, "insert_one", side_effect=RuntimeError("injected failure")):
        with pytest.raises(RuntimeError, match="injected failure"):
            await create_booking(
                tenant_id,
                "rollback-slot",
                "contact-1",
                "Cleaning",
                "rollback-request",
            )

    slot = await Slots(tenant_id).find_one({"_id": "rollback-slot"})
    assert slot is not None
    assert slot["status"] == "held"
    assert slot["hold_owner"] == "rollback-request"
    assert "booking_id" not in slot
    assert await Bookings(tenant_id).count_documents({}) == 0
