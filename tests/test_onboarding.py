from __future__ import annotations

from copy import deepcopy

import pytest
from app.models.base import get_db
from ops.onboard_tenant import TenantConfig, apply_config
from pydantic import ValidationError


def _valid_config() -> dict[str, object]:
    return {
        "tenant_id": "onboarding-clinic",
        "name": "Onboarding Clinic",
        "timezone": "Asia/Kolkata",
        "plan": "starter",
        "locale_default": "hi",
        "wa_number": "919999999999",
        "voice_number": "919999999998",
        "landmark_line": "Near Main Market",
        "location_pin": "https://maps.example.test/clinic",
        "dashboard_url": "https://dashboard.example.test",
        "gstin": "21ABCDE1234F1Z5",
        "whatsapp": {
            "phone_number_id": "sender-id",
            "access_token_env": "VAANI_WA_TOKEN_ONBOARDING",
        },
        "business_hours": [{"day": "monday", "start": "09:00", "end": "18:00"}],
        "holiday_calendar": [],
        "practitioners": [
            {
                "practitioner_id": "onboarding-doctor",
                "name": "Dr Onboarding",
                "services": ["Consultation"],
                "schedule_template": {
                    "monday": [{"start": "09:00", "end": "09:30"}]
                },
            }
        ],
    }


def test_onboarding_rejects_bad_timezone_secret_value_and_overlaps() -> None:
    invalid_timezone = _valid_config()
    invalid_timezone["timezone"] = "Mars/Olympus"
    with pytest.raises(ValidationError, match="valid IANA zone"):
        TenantConfig.model_validate(invalid_timezone)

    embedded_secret = _valid_config()
    embedded_secret["whatsapp"] = {
        "phone_number_id": "sender-id",
        "access_token_env": "secret token value",
    }
    with pytest.raises(ValidationError, match="environment variable name"):
        TenantConfig.model_validate(embedded_secret)

    overlap = _valid_config()
    practitioners = deepcopy(overlap["practitioners"])
    practitioners[0]["schedule_template"]["monday"] = [
        {"start": "09:00", "end": "10:00"},
        {"start": "09:30", "end": "10:30"},
    ]
    overlap["practitioners"] = practitioners
    with pytest.raises(ValidationError, match="overlapping practitioner schedule"):
        TenantConfig.model_validate(overlap)


@pytest.mark.filterwarnings(
    "ignore:datetime.datetime.utcnow.*:DeprecationWarning:mongomock.helpers"
)
async def test_onboarding_apply_is_idempotent_and_preserves_bookings() -> None:
    db = get_db()
    config = TenantConfig.model_validate(_valid_config())
    first = await apply_config(config)
    await db["bookings"].insert_one(
        {
            "_id": "existing-booking",
            "tenant_id": config.tenant_id,
            "status": "confirmed",
        }
    )
    second = await apply_config(config)

    assert first["slots_created"] > 0
    assert second["slots_created"] == 0
    assert await db["tenants"].count_documents({"_id": config.tenant_id}) == 1
    assert await db["practitioners"].count_documents(
        {"tenant_id": config.tenant_id}
    ) == 1
    assert await db["bookings"].find_one({"_id": "existing-booking"}) is not None
