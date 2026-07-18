"""Node 4 — tool router (TRD §1).

For in-scope intents, decides which tool(s) to call before generation:
kb_search for faq_*, slots_get/booking_* for book/reschedule/cancel,
payment_link_create for payment flows. Every side-effect is a tool call
(06-engineering-plan §0, rule 2).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.models.base import get_db
from app.booking.relative_date import resolve
from app.agent.tools.kb_search import kb_search
from app.agent.tools.slots_get import slots_get

logger = logging.getLogger(__name__)


async def tool_router(state: dict[str, Any]) -> dict[str, Any]:
    """Node 4 — tool router (TRD §1).

    For in-scope intents, decides which tool(s) to call before generation.
    """
    intent_val = state.get("intent", "out_of_scope")
    tenant_id = state.get("tenant_id")
    text = state.get("text", "")
    lang = state.get("lang", "en")
    
    tool_results: list[dict[str, Any]] = []

    # 1. KB Search for FAQ intents
    if intent_val.startswith("faq_"):
        logger.info(f"Routing FAQ intent '{intent_val}' to kb_search")
        kb_results = await kb_search(tenant_id, text, k=3)
        tool_results.append({
            "tool": "kb_search",
            "result": kb_results
        })

    # 2. Slots Lookup for Booking intent
    elif intent_val in ("book", "booking_status"):
        logger.info(f"Routing Booking intent '{intent_val}' to slots_get")
        db = get_db()
        
        # Resolve target date from text
        target_date = resolve(text, today=date.today(), lang=lang)
        date_str = target_date.isoformat()

        # Find practitioner (default to first one found for the tenant)
        practitioner = await db["practitioners"].find_one({"tenant_id": tenant_id})
        
        if practitioner:
            practitioner_id = str(practitioner["_id"])
            practitioner_name = practitioner.get("name", "Doctor")
            
            # Fetch slots
            slots = await slots_get(tenant_id, practitioner_id, date_str)
            tool_results.append({
                "tool": "slots_get",
                "result": slots,
                "date": date_str,
                "practitioner_id": practitioner_id,
                "practitioner_name": practitioner_name
            })
        else:
            logger.warning("No practitioners found for tenant, cannot fetch slots")
            tool_results.append({
                "tool": "slots_get",
                "result": [],
                "error": "no_practitioners_found"
            })

    return {"tool_results": tool_results}

