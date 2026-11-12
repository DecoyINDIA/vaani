"""Per-tenant business profile used to word prompts for any kind of business.

Stored on the tenant document under ``business_profile``. Every field is
optional; the defaults are deliberately industry-neutral so a tenant with no
profile still gets correct, unbiased behaviour. Set during onboarding, e.g.::

    "business_profile": {
        "business_type": "salon",
        "customer_term": "client",
        "staff_term": "stylist",
        "restricted_topics": ["medical or skin-treatment advice"],
        "restricted_examples": ["is rash par kaunsi cream lagau?"],
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.models.collections import Tenants

logger = logging.getLogger(__name__)

_MAX_FIELD_CHARS = 80
_MAX_LIST_ITEMS = 8

# Fail closed: a tenant with no configured list still refuses the advice
# categories that are unsafe for an AI front desk to answer in any industry.
DEFAULT_RESTRICTED_TOPICS: tuple[str, ...] = (
    "medical advice, diagnosis or medicine recommendations",
    "legal advice",
    "financial, tax or investment advice",
)
DEFAULT_RESTRICTED_EXAMPLES: tuple[str, ...] = (
    "is dard ke liye kaunsi dawai lu?",
    "kya mujhe is par court case karna chahiye?",
)


@dataclass(frozen=True)
class BusinessProfile:
    name: str = "our business"
    business_type: str = "business"
    customer_term: str = "customer"
    staff_term: str = "team member"
    restricted_topics: tuple[str, ...] = DEFAULT_RESTRICTED_TOPICS
    restricted_examples: tuple[str, ...] = DEFAULT_RESTRICTED_EXAMPLES


def _clean(value: Any, default: str) -> str:
    """Owner-supplied text lands inside prompts: one line, bounded length."""
    if not isinstance(value, str):
        return default
    cleaned = " ".join(value.split()).replace("'", "").replace('"', "")[:_MAX_FIELD_CHARS]
    return cleaned or default


def _clean_list(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return default
    items = tuple(c for c in (_clean(v, "") for v in value[:_MAX_LIST_ITEMS]) if c)
    return items or default


def profile_from_tenant(tenant: dict[str, Any] | None) -> BusinessProfile:
    if not tenant:
        return BusinessProfile()
    raw = tenant.get("business_profile")
    raw = raw if isinstance(raw, dict) else {}
    defaults = BusinessProfile()
    return BusinessProfile(
        name=_clean(tenant.get("name"), defaults.name),
        business_type=_clean(raw.get("business_type"), defaults.business_type),
        customer_term=_clean(raw.get("customer_term"), defaults.customer_term),
        staff_term=_clean(raw.get("staff_term"), defaults.staff_term),
        restricted_topics=_clean_list(raw.get("restricted_topics"), defaults.restricted_topics),
        restricted_examples=_clean_list(
            raw.get("restricted_examples"), defaults.restricted_examples
        ),
    )


async def load_profile(tenant_id: str) -> BusinessProfile:
    """Load the tenant's profile; neutral defaults if it cannot be read."""
    if not tenant_id:
        return BusinessProfile()
    try:
        return profile_from_tenant(await Tenants.find_by_id(tenant_id))
    except Exception as e:
        logger.warning("Failed to load business profile: %s", type(e).__name__)
        return BusinessProfile()
