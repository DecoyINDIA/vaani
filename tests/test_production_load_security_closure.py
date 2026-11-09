"""Production load, latency, security, secret rotation, and independent closure acceptance tests (WP11 / P8)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from app.booking.engine import hold_slot
from app.config import Settings, settings
from app.main import app
from app.models.base import get_db
from app.owner_api.auth import create_access_token
from fastapi.testclient import TestClient
from ops.rotate_auth_secret import rotate_auth_sessions


def test_production_mode_configuration_strict_validation() -> None:
    # 1. Default/short JWT secret rejected in staging/prod
    with pytest.raises(ValueError, match="jwt_secret must be at least 32 characters"):
        Settings(app_env="prod", jwt_secret="short").validate_runtime()

    with pytest.raises(ValueError, match="jwt_secret must be at least 32 characters"):
        Settings(app_env="prod", jwt_secret="changeme").validate_runtime()

    # 2. Mock adapters forbidden in prod
    with pytest.raises(ValueError, match="use_mock_adapters must be false"):
        Settings(
            app_env="prod",
            jwt_secret="a" * 32,
            use_mock_adapters=True,
            use_mock_llm=False,
        ).validate_runtime()

    with pytest.raises(ValueError, match="use_mock_llm must be false"):
        Settings(
            app_env="prod",
            jwt_secret="a" * 32,
            use_mock_adapters=False,
            use_mock_llm=True,
        ).validate_runtime()

    # 3. Missing required credentials rejected
    with pytest.raises(ValueError, match="missing required settings"):
        Settings(
            app_env="prod",
            jwt_secret="a" * 32,
            use_mock_adapters=False,
            use_mock_llm=False,
        ).validate_runtime()

    # 4. Complete valid production configuration passes
    valid = Settings(
        app_env="prod",
        jwt_secret="a" * 32,
        use_mock_adapters=False,
        use_mock_llm=False,
        meta_app_secret="meta_secret",
        meta_webhook_verify_token="meta_token",
        bsp_access_token="bsp_token",
        bsp_waba_id="bsp_waba",
        bsp_phone_number_id="bsp_phone",
        openrouter_api_key="openrouter_key",
        llm_model_classifier="openai/gpt-4o-mini",
        llm_model_responder="anthropic/claude-3.5-sonnet",
        llm_model_embedding="text-embedding-3-small",
        exotel_sid="exotel_sid",
        exotel_api_key="exotel_key",
        exotel_api_token="exotel_token",
        exotel_subdomain="api.exotel.com",
        sarvam_api_key="sarvam_key",
        razorpay_key_id="rzp_key",
        razorpay_key_secret="rzp_secret",
        razorpay_webhook_secret="rzp_webhook_secret",
        razorpay_plan_starter_id="plan_starter",
        razorpay_plan_pro_id="plan_pro",
        xolver_gstin="29ABCDE1234F1Z5",
    )
    valid.validate_runtime()


@pytest.mark.asyncio
async def test_secret_rotation_and_session_revocation() -> None:
    db = get_db()
    tenant_id = "tenant-rotation-test"
    user_id = "user-rotation-staff"
    old_secret = "old_secret_key_at_least_32_chars_long!!"
    new_secret = "new_secret_key_at_least_32_chars_long!!"

    await db["tenants"].insert_one({"_id": tenant_id, "name": "Rotation Clinic"})
    await db["users"].insert_many([
        {
            "_id": "owner-temp",
            "tenant_id": tenant_id,
            "role": "owner",
            "status": "active",
        },
        {
            "_id": user_id,
            "tenant_id": tenant_id,
            "role": "staff",
            "status": "active",
        },
    ])

    client = TestClient(app)

    with patch.object(settings, "jwt_secret", old_secret):
        # 1. Create invitation and consume magic link under old secret
        owner_token = create_access_token(tenant_id, "owner-temp")
        inv_resp = client.post(
            "/api/auth/invitations",
            json={"user_id": user_id, "role": "staff"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert inv_resp.status_code == 200
        magic_token = inv_resp.json()["magic_token"]

        consume_resp = client.post("/api/auth/magic/consume", json={"token": magic_token})
        assert consume_resp.status_code == 200
        tokens = consume_resp.json()
        old_access = tokens["access_token"]
        old_refresh = tokens["refresh_token"]

        # Access token works
        assert client.get(
            "/api/conversations", headers={"Authorization": f"Bearer {old_access}"}
        ).status_code == 200

        # 2. Dry run secret rotation
        dry_run = await rotate_auth_sessions(authorized_by="security_admin", apply=False)
        assert dry_run["status"] == "dry_run"
        assert dry_run["active_sessions_to_revoke"] >= 1

        # 3. Apply session revocation
        applied = await rotate_auth_sessions(authorized_by="security_admin", apply=True)
        assert applied["status"] == "completed"
        assert applied["revoked_sessions_count"] >= 1

        # 4. Old session is revoked -> refresh fails (401)
        assert client.post(
            "/api/auth/refresh", json={"token": old_refresh}
        ).status_code == 401

        # 5. Access token with revoked session fails (401)
        assert client.get(
            "/api/conversations", headers={"Authorization": f"Bearer {old_access}"}
        ).status_code == 401

    # 6. Now switch JWT secret to new secret:
    with patch.object(settings, "jwt_secret", new_secret):
        # Old access token fails signature check (401)
        assert client.get(
            "/api/conversations", headers={"Authorization": f"Bearer {old_access}"}
        ).status_code == 401

        # Fresh invitation & login under new secret succeeds
        new_owner_token = create_access_token(tenant_id, "owner-temp")
        new_inv = client.post(
            "/api/auth/invitations",
            json={"user_id": user_id, "role": "staff"},
            headers={"Authorization": f"Bearer {new_owner_token}"},
        )
        assert new_inv.status_code == 200
        new_magic = new_inv.json()["magic_token"]

        new_consume = client.post("/api/auth/magic/consume", json={"token": new_magic})
        assert new_consume.status_code == 200
        new_tokens = new_consume.json()
        assert client.get(
            "/api/conversations", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
        ).status_code == 200


def test_private_redis_and_worker_healthcheck_isolation() -> None:
    # 1. Verify docker-compose.yml has NO host ports published for redis
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists()
    content = compose_path.read_text(encoding="utf-8")
    assert "redis:" in content
    # Assert 'ports:' does not appear in redis section
    redis_section = content.split("redis:")[1].split("volumes:")[0]
    assert "ports:" not in redis_section
    assert "8000:8000" in content  # Only API has public ingress port

    # 2. Verify worker healthcheck uses python -m app.workers.healthcheck
    assert "app.workers.healthcheck" in content


@pytest.mark.asyncio
async def test_500_concurrent_slot_claims_zero_double_bookings() -> None:
    db = get_db()
    tenant_id = "tenant-load-500"
    slot_id = "slot-concurrent-500"

    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "status": "open",
    })

    # Execute 500 concurrent hold attempts
    results = await asyncio.gather(
        *(hold_slot(tenant_id, slot_id, f"op-{i}") for i in range(500))
    )

    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)

    # Exactly 1 hold succeeds, 499 fail
    assert success_count == 1
    assert failure_count == 499

    # Verify slot is held by the single winner
    slot = await db["slots"].find_one({"_id": slot_id, "tenant_id": tenant_id})
    assert slot is not None
    assert slot["status"] == "held"
    assert slot["hold_owner"].startswith("op-")


@pytest.mark.asyncio
async def test_api_health_endpoint_checks_redis_and_mongo() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "checks" in data
    assert "mongodb" in data["checks"]
    assert "redis" in data["checks"]
