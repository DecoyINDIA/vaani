"""Node 4 — tool router (TRD §1).

For in-scope intents, decides which tool(s) to call before generation:
kb_search for faq_*, slots_get/booking_* for book/reschedule/cancel,
payment_link_create for payment flows. Every side-effect is a tool call
(06-engineering-plan §0, rule 2).
"""

from __future__ import annotations

from typing import Any


async def tool_router(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("tool router — 06-engineering-plan task 3.5")
