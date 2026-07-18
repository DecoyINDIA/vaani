"""Node 7 — handoff manager (TRD §4.4).

Triggers: human_request, 2x low-confidence, medical/complaint, abuse. Sets
conversations.state = human, silences the bot for that thread, fires a WhatsApp
template alert to on-duty staff (<=30s), starts SLA timers. "Resolve & return"
flips state back to bot with a context summary injected. All transitions audited.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent.tools.escalate import escalate

logger = logging.getLogger(__name__)


async def handoff(state: dict[str, Any]) -> dict[str, Any]:
    """Node 7 — handoff manager (TRD §4.4).

    Triggers human escalation and silences the bot.
    """
    tenant_id = state.get("tenant_id")
    conv_id = state.get("conversation_id")
    intent_val = state.get("intent", "low_confidence")

    logger.info(f"Handoff node triggered for conversation {conv_id}")
    
    # Run the escalation tool to silence the bot, alert staff and create escalation row
    await escalate(tenant_id, conv_id, reason=f"Handoff triggered by intent: {intent_val}")

    return {"escalate": True}

