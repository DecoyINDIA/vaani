from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.channels.whatsapp import (
    AmbiguousDeliveryError,
    SuppressedRecipientError,
    WindowClosedError,
)
from app.main import app
from app.models.base import get_db
from app.models.collections import Messages
from app.owner_api.auth import create_access_token
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db():
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


async def _setup_human_conversation(tenant_id: str, conv_id: str, wa_id: str) -> None:
    db = get_db()
    await db["tenants"].insert_one({"_id": tenant_id, "name": "Staff Clinic", "status": "active"})
    await db["users"].insert_one(
        {"_id": "u_staff_1", "tenant_id": tenant_id, "role": "staff", "status": "active"}
    )
    contact_res = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "phone": wa_id,
            "name": "Staff Patient",
        }
    )
    await db["conversations"].insert_one(
        {
            "_id": conv_id,
            "tenant_id": tenant_id,
            "contact_id": str(contact_res.inserted_id),
            "state": "human",
            "channel": "wa",
        }
    )


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code", "expected_msg"),
    [
        (
            WindowClosedError("24h window closed"),
            409,
            "window_closed",
            "The patient's last message was more than 24 hours ago. WhatsApp only allows approved templates now.",
        ),
        (
            SuppressedRecipientError("Contact is suppressed"),
            409,
            "suppressed",
            "This contact has been erased and cannot be messaged.",
        ),
        (
            AmbiguousDeliveryError("Delivery ambiguous"),
            409,
            "delivery_unknown",
            "This reply may already have been sent. Check Delivery issues before retrying.",
        ),
        (
            RuntimeError("Meta network failure 500"),
            502,
            "provider_error",
            "WhatsApp could not deliver the reply. Try again shortly.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_staff_reply_error_mapping(
    exc: Exception, expected_status: int, expected_code: str, expected_msg: str
) -> None:
    tenant_id = "t_staff_err"
    conv_id = "c_err_1"
    wa_id = "919876543220"
    await _setup_human_conversation(tenant_id, conv_id, wa_id)

    client = TestClient(app)
    token = create_access_token(tenant_id, "u_staff_1")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.owner_api.routes.send_freeform", new=AsyncMock(side_effect=exc)):
        resp = client.post(
            f"/api/conversations/{conv_id}/reply",
            headers=headers,
            json={"text": "Hello patient", "request_id": f"req-{expected_code}"},
        )

    assert resp.status_code == expected_status
    body = resp.json()
    assert body["detail"]["code"] == expected_code
    assert body["detail"]["message"] == expected_msg
    # Ensure no outbound message was recorded
    assert await Messages(tenant_id).count_documents({"direction": "outbound"}) == 0
