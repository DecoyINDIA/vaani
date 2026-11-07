from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.main import app
from app.models.base import get_db
from app.owner_api.auth import create_access_token, create_purpose_token, token_hash
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


async def test_invitation_refresh_rotation_logout_and_removed_membership() -> None:
    db = get_db()
    tenant_id = "session-tenant"
    await db["tenants"].insert_one({"_id": tenant_id, "name": "Session Clinic"})
    await db["users"].insert_one(
        {
            "_id": "owner-1",
            "tenant_id": tenant_id,
            "role": "owner",
            "status": "active",
        }
    )
    client = TestClient(app)
    owner_header = {
        "Authorization": f"Bearer {create_access_token(tenant_id, 'owner-1')}"
    }
    invitation = client.post(
        "/api/auth/invitations",
        json={"user_id": "staff-1", "role": "staff"},
        headers=owner_header,
    )
    assert invitation.status_code == 200
    magic_token = invitation.json()["magic_token"]

    consumed = client.post("/api/auth/magic/consume", json={"token": magic_token})
    assert consumed.status_code == 200
    tokens = consumed.json()
    assert client.post("/api/auth/magic/consume", json={"token": magic_token}).status_code == 401
    access_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/conversations", headers=access_header).status_code == 200

    rotated = client.post("/api/auth/refresh", json={"token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    assert client.post(
        "/api/auth/refresh", json={"token": tokens["refresh_token"]}
    ).status_code == 401
    rotated_tokens = rotated.json()

    await db["users"].update_one(
        {"tenant_id": tenant_id, "_id": "staff-1"}, {"$set": {"status": "removed"}}
    )
    assert client.post(
        "/api/auth/refresh", json={"token": rotated_tokens["refresh_token"]}
    ).status_code == 401
    assert client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    ).status_code == 401

    await db["users"].update_one(
        {"tenant_id": tenant_id, "_id": "staff-1"}, {"$set": {"status": "active"}}
    )
    logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    )
    assert logout.status_code == 200
    assert client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    ).status_code == 401


async def test_expired_magic_link_is_rejected() -> None:
    tenant_id = "expired-session-tenant"
    user_id = "expired-user"
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    token, token_id = create_purpose_token(
        tenant_id, user_id, "magic", expired_at
    )
    await get_db()["users"].insert_one(
        {
            "_id": user_id,
            "tenant_id": tenant_id,
            "role": "staff",
            "status": "invited",
            "magic_hash": token_hash(token_id),
            "magic_expires_at": expired_at.replace(tzinfo=None),
        }
    )
    assert TestClient(app).post(
        "/api/auth/magic/consume", json={"token": token}
    ).status_code == 401


async def test_invitation_issuance_and_magic_exchange_are_bounded() -> None:
    db = get_db()
    tenant_id = "rate-limit-tenant"
    await db["tenants"].insert_one({"_id": tenant_id, "name": "Rate Limit Clinic"})
    await db["users"].insert_one(
        {
            "_id": "rate-owner",
            "tenant_id": tenant_id,
            "role": "owner",
            "status": "active",
        }
    )
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {create_access_token(tenant_id, 'rate-owner')}"
    }
    responses = [
        client.post(
            "/api/auth/invitations",
            json={"user_id": "rate-staff", "role": "staff"},
            headers=headers,
        )
        for _ in range(6)
    ]
    assert [response.status_code for response in responses] == [200, 200, 200, 200, 200, 429]

    invalid = [
        client.post("/api/auth/magic/consume", json={"token": "invalid"})
        for _ in range(21)
    ]
    assert all(response.status_code == 401 for response in invalid[:20])
    assert invalid[20].status_code == 429
