from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.main import app
from app.models.base import get_db
from app.owner_api.auth import create_access_token
from fastapi.testclient import TestClient

RouteCase = tuple[str, str, dict[str, Any] | None]

STAFF_ROUTES: tuple[RouteCase, ...] = (
    ("GET", "/api/conversations", None),
    ("GET", "/api/conversations/missing/messages", None),
    ("POST", "/api/conversations/missing/takeover", None),
    (
        "POST",
        "/api/conversations/missing/reply",
        {"text": "Hello", "request_id": "route-probe-reply"},
    ),
    (
        "POST",
        "/api/conversations/missing/return",
        {"summary": "Resolved by staff."},
    ),
    ("GET", "/api/bookings", None),
    (
        "POST",
        "/api/bookings",
        {
            "slot_id": "missing",
            "contact_id": "missing",
            "service": "Consultation",
            "request_id": "route-probe-booking",
        },
    ),
    ("PATCH", "/api/bookings/missing", {"status": "cancelled"}),
    ("GET", "/api/escalations", None),
    ("GET", "/api/kb", None),
    (
        "PUT",
        "/api/kb",
        {"question": "When are you open?", "answer": "09:00 to 17:00"},
    ),
    ("GET", "/api/settings", None),
    ("GET", "/api/metrics/summary", None),
)

OWNER_ONLY_ROUTES: tuple[RouteCase, ...] = (
    (
        "PUT",
        "/api/settings",
        {"name": "Updated Clinic", "landmark_line": "Near Park", "location_pin": "pin"},
    ),
    ("GET", "/api/audit/export", None),
)


@pytest.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})
    for tenant_id in ("route-a", "route-b"):
        await db["tenants"].insert_one({"_id": tenant_id, "name": f"Clinic {tenant_id}"})
        await db["users"].insert_many(
            [
                {
                    "_id": f"owner-{tenant_id}",
                    "tenant_id": tenant_id,
                    "role": "owner",
                    "status": "active",
                },
                {
                    "_id": f"staff-{tenant_id}",
                    "tenant_id": tenant_id,
                    "role": "staff",
                    "status": "active",
                },
            ]
        )
    yield


def _request(
    client: TestClient,
    case: RouteCase,
    token: str | None = None,
) -> Any:
    method, path, payload = case
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(method, path, json=payload, headers=headers)


def test_every_owner_route_rejects_anonymous_requests() -> None:
    client = TestClient(app)
    for case in STAFF_ROUTES + OWNER_ONLY_ROUTES:
        response = _request(client, case)
        assert response.status_code in {401, 403}, (case, response.text)


def test_staff_permissions_are_explicit_for_every_owner_route() -> None:
    client = TestClient(app)
    token = create_access_token("route-a", "staff-route-a")
    for case in STAFF_ROUTES:
        response = _request(client, case, token)
        assert response.status_code not in {401, 403}, (case, response.text)
    for case in OWNER_ONLY_ROUTES:
        response = _request(client, case, token)
        assert response.status_code == 403, (case, response.text)


def test_owner_can_reach_every_owner_route() -> None:
    client = TestClient(app)
    token = create_access_token("route-a", "owner-route-a")
    for case in STAFF_ROUTES + OWNER_ONLY_ROUTES:
        response = _request(client, case, token)
        assert response.status_code not in {401, 403}, (case, response.text)


async def test_cross_tenant_ids_never_mutate_or_disclose_records() -> None:
    db = get_db()
    await db["contacts"].insert_one(
        {"_id": "contact-a", "tenant_id": "route-a", "wa_id": "911111111111"}
    )
    await db["conversations"].insert_one(
        {
            "_id": "conversation-a",
            "tenant_id": "route-a",
            "contact_id": "contact-a",
            "state": "bot",
        }
    )
    await db["messages"].insert_one(
        {
            "_id": "message-a",
            "tenant_id": "route-a",
            "conversation_id": "conversation-a",
            "text": "tenant A secret",
        }
    )
    await db["slots"].insert_one(
        {"_id": "slot-a", "tenant_id": "route-a", "status": "booked", "booking_id": "booking-a"}
    )
    await db["bookings"].insert_one(
        {
            "_id": "booking-a",
            "tenant_id": "route-a",
            "slot_id": "slot-a",
            "contact_id": "contact-a",
            "status": "confirmed",
        }
    )
    client = TestClient(app)
    token = create_access_token("route-b", "owner-route-b")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/conversations", headers=headers).json() == []
    assert client.get("/api/conversations/conversation-a/messages", headers=headers).json() == []
    assert client.get("/api/bookings", headers=headers).json() == []
    assert client.post("/api/conversations/conversation-a/takeover", headers=headers).status_code == 404
    assert client.post(
        "/api/conversations/conversation-a/return",
        headers=headers,
        json={"summary": "cross tenant"},
    ).status_code == 404
    assert client.patch(
        "/api/bookings/booking-a", headers=headers, json={"status": "cancelled"}
    ).status_code == 404
    assert client.put(
        "/api/settings",
        headers=headers,
        json={"name": "Clinic B Changed", "landmark_line": "B", "location_pin": "B"},
    ).status_code == 200

    conversation = await db["conversations"].find_one({"_id": "conversation-a"})
    booking = await db["bookings"].find_one({"_id": "booking-a"})
    tenant_a = await db["tenants"].find_one({"_id": "route-a"})
    tenant_b = await db["tenants"].find_one({"_id": "route-b"})
    assert conversation is not None and conversation["state"] == "bot"
    assert booking is not None and booking["status"] == "confirmed"
    assert tenant_a is not None and tenant_a["name"] == "Clinic route-a"
    assert tenant_b is not None and tenant_b["name"] == "Clinic B Changed"


async def test_growing_lists_are_sorted_and_paginated() -> None:
    db = get_db()
    base = datetime(2026, 11, 7, tzinfo=UTC).replace(tzinfo=None)
    await db["conversations"].insert_many(
        [
            {
                "_id": f"page-{index}",
                "tenant_id": "route-a",
                "state": "bot",
                "last_msg_at": base + timedelta(minutes=index),
            }
            for index in range(3)
        ]
    )
    token = create_access_token("route-a", "staff-route-a")
    response = TestClient(app).get(
        "/api/conversations?limit=1&offset=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert [item["_id"] for item in response.json()] == ["page-1"]
