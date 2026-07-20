from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.config import settings
from app.gateway.middleware import verify_meta_signature
from app.gateway.razorpay import verify_razorpay_signature
from app.main import app
from app.models.base import get_db
from app.models.collections import Bookings, Slots
from app.owner_api.auth import create_access_token
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    # Seed a test tenant
    await get_db()["tenants"].insert_one({
        "_id": "t_test",
        "name": "Test Clinic",
        "wa_number": "919999999999",
        "landmark_line": "Near Park",
        "location_pin": "https://maps.google.com"
    })
    yield

def test_webhook_verify_fails_closed():
    # If app_env is prod or staging, lack of secret must return False
    old_env = settings.app_env
    old_secret = settings.meta_app_secret
    old_rz_secret = settings.razorpay_webhook_secret
    try:
        settings.app_env = "prod"
        settings.meta_app_secret = ""
        settings.razorpay_webhook_secret = ""
        
        # Meta signature check should fail closed
        assert verify_meta_signature(b"{}", "sha256=abc") is False
        
        # Razorpay signature check should fail closed
        assert verify_razorpay_signature(b"{}", "abc") is False
    finally:
        settings.app_env = old_env
        settings.meta_app_secret = old_secret
        settings.razorpay_webhook_secret = old_rz_secret

def test_owner_api_jwt_access():
    client = TestClient(app)
    
    # 1. Unauthenticated requests should be rejected
    resp = client.get("/api/conversations")
    assert resp.status_code in (401, 403)
    
    # 2. Invalid JWT should be rejected
    resp = client.get("/api/conversations", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401
    
    # 3. Valid JWT should allow request
    token = create_access_token(tenant_id="t_test", user_id="u_test")
    resp = client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_atomic_booking_rollback():
    # Insert a slot in held state
    slot_id = "slot_atomic_test"
    tenant_id = "t_test"
    now = datetime.now(UTC).replace(tzinfo=None)
    await Slots(tenant_id).insert_one({
        "_id": slot_id,
        "status": "held",
        "hold_expiry": now + timedelta(minutes=10)
    })
    
    # Force Bookings collection to throw on insert_one
    from unittest.mock import patch

    from app.booking.engine import confirm_booking
    
    with patch.object(Bookings, "insert_one", side_effect=Exception("DB write failure")):
        with pytest.raises(Exception, match="DB write failure"):
            await confirm_booking(tenant_id, slot_id, "contact_123", "Tooth Extraction")
            
    # Verify slot was rolled back to "held"
    slot = await Slots(tenant_id).find_one({"_id": slot_id})
    assert slot is not None
    assert slot["status"] == "held"


@pytest.mark.asyncio
async def test_cross_tenant_isolation():
    # Insert a conversation for tenant t_test
    await get_db()["conversations"].insert_one({
        "_id": "conv_test",
        "tenant_id": "t_test",
        "state": "bot"
    })
    
    client = TestClient(app)
    
    # Request with token for tenant B (t_other)
    token_other = create_access_token(tenant_id="t_other", user_id="u_test")
    resp = client.get("/api/conversations", headers={"Authorization": f"Bearer {token_other}"})
    assert resp.status_code == 200
    # Should be empty since t_other has no conversations
    assert resp.json() == []
    
    # Request with token for tenant t_test
    token_test = create_access_token(tenant_id="t_test", user_id="u_test")
    resp = client.get("/api/conversations", headers={"Authorization": f"Bearer {token_test}"})
    assert resp.status_code == 200
    # Should return the seeded conversation
    assert len(resp.json()) == 1
    assert resp.json()[0]["_id"] == "conv_test"
