"""Node 3 — input scope gate (TRD §4.2, gate 1).

Routes by intent. medical_question / out_of_scope / abuse / complaint never reach
the LLM responder — they go to static templates + escalate flags. This is the
first of the two mandatory gates that make Meta-policy compliance a code path.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.base import get_db
from app.agent.templates import get_template

logger = logging.getLogger(__name__)


async def scope_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Node 3 — input scope gate (TRD §4.2, gate 1).

    Routes by intent. medical_question / out_of_scope / abuse / complaint never reach
    the LLM responder — they go to static templates + escalate flags.
    """
    intent_val = state.get("intent", "out_of_scope")
    confidence = state.get("confidence", 1.0)
    lang = state.get("lang", "en")
    conv_id = state.get("conversation_id")
    
    # 1. Check for consecutive low confidence (< 0.70)
    if confidence < 0.70:
        logger.info(f"Low confidence detected: {confidence}")
        consecutive_low = False
        try:
            db = get_db()
            # Find the last inbound message in this conversation
            last_msg = await db["messages"].find_one(
                {"conversation_id": conv_id, "direction": "inbound"},
                sort=[("ts", -1)]
            )
            if last_msg and last_msg.get("confidence", 1.0) < 0.70:
                consecutive_low = True
        except Exception as e:
            logger.warning(f"Error querying last message for confidence fallback: {e}")
            
        if consecutive_low:
            logger.info("Consecutive low confidence! Triggering escalation.")
            return {
                "escalate": True,
                "response": get_template("out_of_scope", lang)
            }

    # 2. Check for abuse or complaint (allow 1 de-escalation, then silent handoff)
    if intent_val in ("abuse", "complaint"):
        has_previous_incident = False
        try:
            db = get_db()
            previous = await db["messages"].find_one(
                {
                    "conversation_id": conv_id,
                    "direction": "inbound",
                    "intent": {"$in": ["abuse", "complaint"]}
                }
            )
            if previous:
                has_previous_incident = True
        except Exception as e:
            logger.warning(f"Error checking previous abuse/complaint: {e}")

        if has_previous_incident:
            logger.info(f"Repeated {intent_val}! Escalating silently.")
            return {
                "escalate": True,
                "response": get_template("de_escalation", lang)
            }
        else:
            logger.info(f"First {intent_val} encounter. Sending de-escalation template.")
            return {
                "response": get_template("de_escalation", lang)
            }

    # 3. Medical question -> static refusal + escalate to staff
    if intent_val == "medical_question":
        logger.info("Medical question detected. Refusing and escalating.")
        return {
            "escalate": True,
            "response": get_template("medical_refusal", lang)
        }

    # 4. Out of scope -> static template (no escalation unless confidence is low)
    if intent_val == "out_of_scope":
        logger.info("Out of scope message detected. Returning capabilities menu.")
        return {
            "response": get_template("out_of_scope", lang)
        }

    # In-scope intent, route to tool_router/responder
    return {}

