from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from app.agent.graph import build_graph
from app.agent.llm import query_llm
from app.config import Settings, settings
from app.gateway.middleware import verify_meta_signature
from app.gateway.razorpay import verify_razorpay_signature
from app.main import app
from app.models.base import get_db
from app.models.collections import Bookings, Slots
from app.owner_api.auth import create_access_token
from bson import ObjectId
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
    await get_db()["users"].insert_one({
        "_id": "u_test", "tenant_id": "t_test", "role": "owner", "status": "active"
    })
    await get_db()["users"].insert_one({
        "_id": "u_staff", "tenant_id": "t_test", "role": "staff", "status": "active"
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


def test_unsafe_production_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="jwt_secret"):
        Settings(app_env="prod", jwt_secret="changeme").validate_runtime()

    valid = Settings(
        app_env="prod",
        jwt_secret="x" * 32,
        meta_app_secret="x",
        meta_webhook_verify_token="x",
        bsp_access_token="x",
        bsp_waba_id="x",
        bsp_phone_number_id="x",
        openrouter_api_key="x",
        llm_model_classifier="classifier",
        llm_model_responder="responder",
        llm_model_embedding="embedding",
        exotel_sid="x",
        exotel_api_key="x",
        exotel_api_token="x",
        exotel_subdomain="x",
        razorpay_key_id="x",
        razorpay_key_secret="x",
        razorpay_webhook_secret="x",
        razorpay_plan_starter_id="plan_starter",
        razorpay_plan_pro_id="plan_pro",
        xolver_gstin="x",
        sarvam_api_key="x",
        use_mock_adapters=False,
    )
    valid.validate_runtime()
    invalid_dimensions = valid.model_copy(update={"kb_embedding_dimensions": 0})
    with pytest.raises(ValueError, match="kb_embedding_dimensions"):
        invalid_dimensions.validate_runtime()
    with pytest.raises(ValueError, match="use_mock_llm"):
        valid.model_copy(update={"use_mock_llm": True}).validate_runtime()


@pytest.mark.asyncio
async def test_llm_mock_requires_explicit_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        await query_llm("hello", "classifier")

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def post(self, *_args: object, **_kwargs: object) -> None:
            raise httpx.ReadTimeout("synthetic outage")

    monkeypatch.setattr("app.agent.llm.httpx.AsyncClient", Client)
    with pytest.raises(httpx.ReadTimeout):
        await query_llm("hello", "classifier")

    monkeypatch.setattr(settings, "use_mock_llm", True)
    assert "greet" in await query_llm("User message: 'hello'", "classifier", "classify")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["classifier", "responder"])
async def test_llm_failures_create_real_handoff(
    monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    conversation_id = f"llm-{failure_stage}-failure"
    await get_db()["conversations"].insert_one(
        {
            "_id": conversation_id,
            "tenant_id": "t_test",
            "state": "bot",
            "contact_id": "llm-failure-contact",
        }
    )
    if failure_stage == "classifier":
        monkeypatch.setattr(
            "app.agent.nodes.intent.query_llm",
            AsyncMock(side_effect=RuntimeError("synthetic provider failure")),
        )
    else:
        monkeypatch.setattr(
            "app.agent.nodes.intent.query_llm",
            AsyncMock(return_value='{"intent":"faq_hours","confidence":0.99}'),
        )
        monkeypatch.setattr(
            "app.agent.nodes.tool_router.kb_search",
            AsyncMock(
                return_value=[
                    {
                        "question": "Hours?",
                        "answer": "Nine to five.",
                        "source_ref": "faq_hours",
                    }
                ]
            ),
        )
        monkeypatch.setattr(
            "app.agent.nodes.responder.query_llm",
            AsyncMock(side_effect=RuntimeError("synthetic provider failure")),
        )

    result = await build_graph().ainvoke(
        {
            "tenant_id": "t_test",
            "conversation_id": conversation_id,
            "channel": "wa",
            "text": "What are your hours?",
        }
    )

    escalation = await get_db()["escalations"].find_one(
        {"tenant_id": "t_test", "conversation_id": conversation_id}
    )
    assert result["escalate"] is True
    assert "our team" in result["response"]
    assert escalation["reason"].endswith("llm_unavailable")
    conversation = await get_db()["conversations"].find_one({"_id": conversation_id})
    assert conversation["state"] == "human"

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


def test_staff_cannot_change_owner_settings() -> None:
    token = create_access_token(tenant_id="t_test", user_id="u_staff")
    response = TestClient(app).put(
        "/api/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Changed", "landmark_line": "x", "location_pin": "x"},
    )
    assert response.status_code == 403


def test_generated_object_ids_are_serialized() -> None:
    conversation_id = ObjectId()

    async def seed() -> None:
        await get_db()["conversations"].insert_one(
            {"_id": conversation_id, "tenant_id": "t_test", "state": "bot"}
        )

    import asyncio

    asyncio.run(seed())
    token = create_access_token(tenant_id="t_test", user_id="u_test")
    response = TestClient(app).get(
        "/api/conversations", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()[0]["_id"] == str(conversation_id)

@pytest.mark.asyncio
async def test_atomic_booking_rollback():
    # Insert a slot in held state
    slot_id = "slot_atomic_test"
    tenant_id = "t_test"
    now = datetime.now(UTC).replace(tzinfo=None)
    await Slots(tenant_id).insert_one({
        "_id": slot_id,
        "status": "held",
        "hold_owner": "op-test",
        "hold_expiry": now + timedelta(minutes=10)
    })
    
    # Force Bookings collection to throw on insert_one
    from unittest.mock import patch

    from app.booking.engine import confirm_booking
    
    with patch.object(Bookings, "insert_one", side_effect=Exception("DB write failure")):
        with pytest.raises(Exception, match="DB write failure"):
            await confirm_booking(
                tenant_id, slot_id, "contact_123", "Tooth Extraction", "op-test"
            )
            
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
    
    await get_db()["users"].insert_one({
        "_id": "u_other", "tenant_id": "t_other", "role": "owner", "status": "active"
    })

    # Request with token for tenant B (t_other)
    token_other = create_access_token(tenant_id="t_other", user_id="u_other")
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
