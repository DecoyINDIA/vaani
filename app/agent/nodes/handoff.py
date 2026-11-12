"""Node 7 — handoff manager (TRD §4.4).

Triggers: human_request, 2x low-confidence, restricted advice/complaint, abuse. Sets
conversations.state = human, silences the bot for that thread, fires a WhatsApp
template alert to on-duty staff (<=30s), starts SLA timers. "Resolve & return"
flips state back to bot with a context summary injected. All transitions audited.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent.state import AgentState
from app.agent.tools.escalate import escalate

logger = logging.getLogger(__name__)


async def handoff(state: AgentState) -> dict[str, Any]:
    """Node 7 — handoff manager (TRD §4.4).

    Triggers human escalation and silences the bot.
    """
    tenant_id: str = state.get("tenant_id") or ""
    conv_id: str = state.get("conversation_id") or ""
    intent_val = state.get("intent", "low_confidence")
    agent_error = state.get("agent_error")

    logger.info(f"Handoff node triggered for conversation {conv_id}")
    
    if agent_error:
        from app import audit

        await audit.record(
            tenant_id,
            actor="system",
            event_type="operational_alert",
            payload={
                "kind": "provider_failure",
                "provider": "openrouter_llm",
                "reason": str(agent_error),
            },
            operation_key=f"llm-failure-alert:{conv_id}",
        )

    # Run the escalation tool to silence the bot, alert staff and create escalation row
    result = await escalate(
        tenant_id,
        conv_id,
        reason=(
            f"Handoff triggered by system error: {agent_error}"
            if agent_error
            else f"Handoff triggered by intent: {intent_val}"
        ),
        lang=str(state.get("lang", "en")),
    )

    safety_response = state.get("response") if intent_val in {
        "restricted_advice",
        "complaint",
        "abuse",
    } else None
    response = safety_response or result.get("patient_message") or state.get("response")
    return {"escalate": True, **({"response": response} if response else {})}

