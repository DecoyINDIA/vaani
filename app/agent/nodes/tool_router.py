"""Node 4 — tool router (TRD §1).

For in-scope intents, decides which tool(s) to call before generation:
kb_search for faq_*, slots_get/booking_* for book/reschedule/cancel,
payment_link_create for payment flows. Every side-effect is a tool call
(06-engineering-plan §0, rule 2).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from app.agent.state import AgentState
from app.agent.templates import get_template
from app.agent.tools.kb_search import kb_search
from app.agent.tools.slots_get import slots_get
from app.booking.relative_date import resolve_or_none
from app.booking.timefmt import tenant_timezone
from app.models.collections import Practitioners, Tenants

logger = logging.getLogger(__name__)


async def tool_router(state: AgentState) -> dict[str, Any]:
    """Node 4 — tool router (TRD §1).

    For in-scope intents, decides which tool(s) to call before generation.
    """
    intent_val = state.get("intent", "out_of_scope")
    tenant_id: str = state.get("tenant_id") or ""
    text = state.get("text", "")
    lang = state.get("lang", "en")

    tool_results: list[dict[str, Any]] = []

    # 1. KB Search for FAQ intents
    if intent_val.startswith("faq_"):
        logger.info(f"Routing FAQ intent '{intent_val}' to kb_search")
        kb_results = await kb_search(
            tenant_id,
            text,
            k=3,
            fallback_key=intent_val,
        )
        tool_results.append({
            "tool": "kb_search",
            "result": kb_results,
        })
        if not kb_results:
            return {
                "tool_results": tool_results,
                "escalate": True,
                "response": get_template("handoff_ack", lang),
            }

    # 2. Slots Lookup for Booking intent
    elif intent_val in ("book", "reschedule"):
        logger.info(f"Routing Booking intent '{intent_val}' to slots_get")

        tenant = await Tenants.find_by_id(tenant_id) if tenant_id else None
        timezone = tenant_timezone(tenant)
        today_local = datetime.now(UTC).astimezone(timezone).date()

        parser_date = resolve_or_none(text, today=today_local, lang=lang)
        model_req_date = state.get("req_date")

        target_date: date
        if parser_date is not None:
            if model_req_date and model_req_date != parser_date.isoformat():
                logger.info("Parser and model date disagreement: preferring parser date")
            target_date = parser_date
        elif model_req_date:
            try:
                target_date = date.fromisoformat(model_req_date)
            except ValueError:
                target_date = today_local
        else:
            target_date = today_local

        date_str = target_date.isoformat()
        req_time = state.get("req_time")

        # Find practitioner (default to first one found for the tenant)
        practitioner = await Practitioners(tenant_id).find_one({})

        if practitioner:
            practitioner_id = str(practitioner["_id"])
            practitioner_name = practitioner.get("name") or "our team"

            # Fetch slots
            slots = await slots_get(tenant_id, practitioner_id, date_str)

            if req_time and isinstance(slots, list):
                try:
                    req_h, req_m = map(int, req_time.split(":"))
                    req_mins = req_h * 60 + req_m

                    def _slot_distance(s: dict[str, Any]) -> tuple[int, int]:
                        st = datetime.fromisoformat(str(s["start"])).astimezone(timezone)
                        slot_mins = st.hour * 60 + st.minute
                        diff = abs(slot_mins - req_mins)
                        return (diff, slot_mins)

                    slots = sorted(slots, key=_slot_distance)
                except Exception as sort_err:
                    logger.warning("Failed to sort slots by requested time: %s", sort_err)

            tool_dict: dict[str, Any] = {
                "tool": "slots_get",
                "result": slots,
                "date": date_str,
                "practitioner_id": practitioner_id,
                "practitioner_name": practitioner_name,
            }
            if req_time:
                tool_dict["requested_time"] = req_time
            tool_results.append(tool_dict)
        else:
            logger.warning("No practitioners found for tenant, cannot fetch slots")
            tool_dict = {
                "tool": "slots_get",
                "result": [],
                "error": "no_practitioners_found",
                "date": date_str,
            }
            if req_time:
                tool_dict["requested_time"] = req_time
            tool_results.append(tool_dict)

    return {"tool_results": tool_results}

