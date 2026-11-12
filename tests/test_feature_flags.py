"""Tests for feature-flagged runtime validation and conditional router mounts (W1-08)."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.main import create_app
from fastapi import FastAPI


def _base_valid_staging_kwargs() -> dict[str, object]:
    """Always-required settings for staging/prod when all optional flags are off."""
    return {
        "app_env": "staging",
        "jwt_secret": "a" * 32,
        "use_mock_adapters": False,
        "use_mock_llm": False,
        "meta_app_secret": "meta_secret_123",
        "meta_webhook_verify_token": "meta_token_123",
        "openrouter_api_key": "openrouter_key_123",
        "llm_model_classifier": "model_clf",
        "llm_model_responder": "model_resp",
        "llm_model_embedding": "model_emb",
        "enable_voice": False,
        "enable_payments": False,
        "enable_billing": False,
    }


def test_whatsapp_only_staging_boots_with_flags_off() -> None:
    settings = Settings(**_base_valid_staging_kwargs())
    # Must not raise
    settings.validate_runtime()


def test_enable_voice_without_exotel_raises_naming_missing_settings() -> None:
    kwargs = _base_valid_staging_kwargs()
    kwargs["enable_voice"] = True
    settings = Settings(**kwargs)
    with pytest.raises(ValueError, match="missing required settings.*exotel_sid"):
        settings.validate_runtime()


def test_enable_voice_with_sarvam_requires_sarvam_api_key() -> None:
    kwargs = _base_valid_staging_kwargs()
    kwargs.update({
        "enable_voice": True,
        "exotel_sid": "sid",
        "exotel_api_key": "key",
        "exotel_api_token": "token",
        "exotel_subdomain": "sub",
        "stt_provider": "sarvam",
        "sarvam_api_key": "",
    })
    settings = Settings(**kwargs)
    with pytest.raises(ValueError, match="sarvam_api_key is required by stt_provider"):
        settings.validate_runtime()


def test_enable_billing_without_gstin_raises_naming_missing_settings() -> None:
    kwargs = _base_valid_staging_kwargs()
    kwargs["enable_billing"] = True
    settings = Settings(**kwargs)
    with pytest.raises(ValueError, match="missing required settings.*xolver_gstin"):
        settings.validate_runtime()


def test_enable_payments_with_razorpay_credentials_passes() -> None:
    kwargs = _base_valid_staging_kwargs()
    kwargs.update({
        "enable_payments": True,
        "razorpay_key_id": "rzp_id_123",
        "razorpay_key_secret": "rzp_secret_123",
        "razorpay_webhook_secret": "rzp_webhook_123",
    })
    settings = Settings(**kwargs)
    settings.validate_runtime()


def test_default_jwt_secret_rejected_with_all_flags_off() -> None:
    kwargs = _base_valid_staging_kwargs()
    kwargs["jwt_secret"] = "changeme"
    settings = Settings(**kwargs)
    with pytest.raises(ValueError, match="jwt_secret must be at least 32 characters"):
        settings.validate_runtime()


def _collect_paths(app: FastAPI) -> list[str]:
    paths: list[str] = []
    for r in app.routes:
        if hasattr(r, "include_context") and hasattr(r, "original_router"):
            prefix = getattr(r.include_context, "prefix", "")
            for s in getattr(r.original_router, "routes", []):
                paths.append(prefix + getattr(s, "path", ""))
        elif hasattr(r, "path"):
            paths.append(str(r.path))
    return paths


def test_router_mounting_respects_feature_flags() -> None:
    # 1. With all flags off: no exotel or razorpay routes
    flags_off = Settings(
        app_env="dev",
        enable_voice=False,
        enable_payments=False,
        enable_billing=False,
    )
    app_off = create_app(flags_off)
    routes_off = _collect_paths(app_off)

    assert not any(p.startswith("/webhooks/exotel") for p in routes_off)
    assert not any(p.startswith("/webhooks/razorpay") for p in routes_off)
    assert any(p.startswith("/webhooks/meta") for p in routes_off)

    # 2. With voice and payments on: exotel and razorpay mounted
    flags_on = Settings(
        app_env="dev",
        enable_voice=True,
        enable_payments=True,
        enable_billing=False,
    )
    app_on = create_app(flags_on)
    routes_on = _collect_paths(app_on)

    assert any(p.startswith("/webhooks/exotel") for p in routes_on)
    assert any(p.startswith("/webhooks/razorpay") for p in routes_on)
    assert any(p.startswith("/webhooks/meta") for p in routes_on)
