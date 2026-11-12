"""Central settings — the single place every environment variable is read.

Grouped to mirror `.env.example` and the TRD ADRs. Nothing else in the codebase
should call `os.environ`; import `settings` from here instead.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-only-insecure-secret-do-not-deploy"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_env: Literal["dev", "staging", "prod"] = "dev"
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30
    use_mock_adapters: bool = False
    use_mock_llm: bool = False
    enable_voice: bool = False
    enable_payments: bool = False
    enable_billing: bool = False

    # --- Datastore (ADR-03: MongoDB Atlas ap-south-1 + Redis) ---
    mongodb_uri: str = "mongodb://localhost:27017/vaani"
    redis_url: str = "redis://localhost:6379/0"

    # --- WhatsApp / BSP (ADR-04: Meta Cloud API via BSP) ---
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = ""
    bsp_access_token: str = ""
    bsp_waba_id: str = ""
    bsp_phone_number_id: str = ""

    # --- LLM (ADR-02: OpenRouter, model-pinned per node) ---
    openrouter_api_key: str = ""
    llm_model_classifier: str = ""       # small/cheap model, temp 0
    llm_model_responder: str = ""        # frontier model
    llm_model_embedding: str = ""        # OpenRouter embedding model
    llm_model_fallback_provider: str = ""
    llm_timeout_seconds: float = 8.0
    llm_json_mode: bool = True
    kb_text_index: str = "kb_text"
    kb_vector_index: str = "kb_vector"
    kb_embedding_dimensions: int = 1536

    # --- Voice (ADR-05, Phase 2: Exotel + Sarvam-first STT/TTS) ---
    exotel_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_subdomain: str = ""
    voice_public_base_url: str = ""
    stt_provider: Literal["sarvam", "deepgram", "google"] = "sarvam"
    tts_provider: Literal["sarvam", "elevenlabs"] = "sarvam"
    sarvam_api_key: str = ""
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""

    # --- Payments (Razorpay: subscriptions, UPI Autopay, payment links) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_plan_starter_id: str = ""
    razorpay_plan_pro_id: str = ""

    # --- Billing / GST (F-17) ---
    xolver_gstin: str = ""
    invoice_sac_code: str = "998313"

    # --- Observability ---
    sentry_dsn: str = ""
    alerts_destination_url: str = ""

    # --- Ops ---
    audit_log_retention_days: int = 90
    media_purge_days: int = 30

    def validate_runtime(self) -> None:
        """Reject unsafe staging/production configuration before serving work."""
        if self.app_env == "dev":
            return

        errors: list[str] = []
        if len(self.jwt_secret) < 32 or self.jwt_secret in {"changeme", _DEV_JWT_SECRET}:
            errors.append("jwt_secret must be at least 32 characters and not a default")
        if self.use_mock_adapters:
            errors.append("use_mock_adapters must be false")
        if self.use_mock_llm:
            errors.append("use_mock_llm must be false")

        always_required = (
            "meta_app_secret",
            "meta_webhook_verify_token",
            "openrouter_api_key",
            "llm_model_classifier",
            "llm_model_responder",
            "llm_model_embedding",
        )
        missing = [name for name in always_required if not getattr(self, name)]

        if self.enable_voice:
            voice_required = (
                "exotel_sid",
                "exotel_api_key",
                "exotel_api_token",
                "exotel_subdomain",
            )
            missing.extend(name for name in voice_required if not getattr(self, name))
            if self.stt_provider == "sarvam" and not self.sarvam_api_key:
                errors.append("sarvam_api_key is required by stt_provider")
            if self.stt_provider == "deepgram" and not self.deepgram_api_key:
                errors.append("deepgram_api_key is required by stt_provider")
            if self.tts_provider == "sarvam" and not self.sarvam_api_key:
                errors.append("sarvam_api_key is required by tts_provider")
            if self.tts_provider == "elevenlabs" and not self.elevenlabs_api_key:
                errors.append("elevenlabs_api_key is required by tts_provider")

        if self.enable_payments or self.enable_billing:
            payments_required = (
                "razorpay_key_id",
                "razorpay_key_secret",
                "razorpay_webhook_secret",
            )
            missing.extend(name for name in payments_required if not getattr(self, name))

        if self.enable_billing:
            billing_required = (
                "razorpay_plan_starter_id",
                "razorpay_plan_pro_id",
                "xolver_gstin",
            )
            missing.extend(name for name in billing_required if not getattr(self, name))

        if missing:
            errors.append(f"missing required settings: {', '.join(missing)}")
        if self.kb_embedding_dimensions < 1:
            errors.append("kb_embedding_dimensions must be positive")

        if errors:
            raise ValueError("Unsafe runtime configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()


settings = get_settings()
