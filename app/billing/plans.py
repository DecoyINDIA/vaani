"""Single source of truth for public billing plans and provider mappings."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class Plan:
    code: str
    monthly_price_paise: int
    included_conversations: int | None = None
    conversation_overage_paise: int = 0
    included_bookings: int | None = None
    booking_overage_paise: int = 0
    included_voice_seconds: int | None = None
    voice_overage_paise_per_minute: int = 0


PLANS: dict[str, Plan] = {
    "starter": Plan(
        code="starter",
        monthly_price_paise=299_900,
        included_conversations=1_000,
        conversation_overage_paise=200,
        included_bookings=50,
        booking_overage_paise=4_900,
    ),
    "pro": Plan(
        code="pro",
        monthly_price_paise=699_900,
        included_voice_seconds=300 * 60,
        voice_overage_paise_per_minute=400,
    ),
}


def get_plan(code: str) -> Plan:
    try:
        return PLANS[code.lower()]
    except KeyError:
        raise ValueError(f"Unknown billing plan: {code}") from None


def plan_from_provider_id(provider_plan_id: str) -> Plan:
    mapping = {
        settings.razorpay_plan_starter_id: "starter",
        settings.razorpay_plan_pro_id: "pro",
    }
    if not provider_plan_id or provider_plan_id not in mapping:
        raise ValueError(f"Unknown Razorpay plan ID: {provider_plan_id}")
    return get_plan(mapping[provider_plan_id])
