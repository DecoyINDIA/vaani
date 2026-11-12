"""Tenant profile helper for agent prompts (TRD §4.2, W1-02)."""

from __future__ import annotations

import logging
from typing import Any

from app.models.collections import Tenants

logger = logging.getLogger(__name__)

_DEFAULT_NAME = "the clinic"
_DEFAULT_BUSINESS_TYPE = "clinic"
_MAX_CHARS = 80


def _clean_str(val: Any, default: str) -> str:
    if not isinstance(val, str):
        return default
    cleaned = " ".join(val.split())[:_MAX_CHARS]
    return cleaned or default


async def get_tenant_profile(tenant_id: str) -> dict[str, str]:
    """Return sanitized tenant profile dict with keys 'name' and 'business_type'.

    Defaults to 'the clinic' and 'clinic'. Newlines stripped, capped at 80 characters.
    """
    defaults = {"name": _DEFAULT_NAME, "business_type": _DEFAULT_BUSINESS_TYPE}
    if not tenant_id:
        return defaults
    try:
        tenant = await Tenants.find_by_id(tenant_id)
        if not tenant:
            return defaults
        name = tenant.get("name") or _DEFAULT_NAME
        biz_type = tenant.get("business_type")
        if not biz_type and isinstance(tenant.get("business_profile"), dict):
            biz_type = tenant["business_profile"].get("business_type")
        biz_type = biz_type or _DEFAULT_BUSINESS_TYPE
        return {
            "name": _clean_str(name, _DEFAULT_NAME),
            "business_type": _clean_str(biz_type, _DEFAULT_BUSINESS_TYPE),
        }
    except Exception as e:
        logger.warning("Failed to load tenant profile for %s: %s", tenant_id, e)
        return defaults
