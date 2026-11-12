from __future__ import annotations

import pytest
from app.main import app
from app.models.base import get_db
from app.owner_api.auth import create_access_token
from app.owner_api.routes import SETTINGS_FIELDS
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


@pytest.mark.asyncio
async def test_get_settings_allow_list_filters_sensitive_fields() -> None:
    tenant_id = "t_settings_test"
    db = get_db()
    await db["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Settings Clinic",
            "timezone": "Asia/Kolkata",
            "plan": "starter",
            "locale_default": "en",
            "wa_number": "+919876543210",
            "voice_number": "+918012345678",
            "landmark_line": "Near Metro Station",
            "location_pin": "https://maps.google.com/?q=test",
            "business_hours": [{"day": 0, "open": "09:00", "close": "18:00"}],
            "holiday_calendar": ["2026-12-25"],
            # Sensitive / internal fields that MUST be filtered out
            "whatsapp": {"access_token_env": "WHATSAPP_SECRET_KEY", "phone_number_id": "phone_123"},
            "gstin": "29ABCDE1234F1Z5",
            "razorpay_account_id": "acc_secret_999",
            "internal_secret_flag": True,
            "billing_customer_id": "cust_123",
        }
    )
    await db["users"].insert_one(
        {"_id": "u_staff_settings", "tenant_id": tenant_id, "role": "staff", "status": "active"}
    )

    client = TestClient(app)
    token = create_access_token(tenant_id, "u_staff_settings")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/settings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Public allowed fields are present
    assert data["name"] == "Settings Clinic"
    assert data["timezone"] == "Asia/Kolkata"
    assert data["_id"] == tenant_id

    # Sensitive fields are completely absent
    assert "whatsapp" not in data
    assert "gstin" not in data
    assert "razorpay_account_id" not in data
    assert "internal_secret_flag" not in data
    assert "billing_customer_id" not in data

    # Every key in data must be in SETTINGS_FIELDS
    assert set(data.keys()).issubset(set(SETTINGS_FIELDS))
