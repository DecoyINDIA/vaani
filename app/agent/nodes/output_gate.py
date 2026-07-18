"""Node 6 — output scope check (TRD §4.2, gate 2).

Post-generation: reject any uncited factual claim (fee/time/service/address) and
any content outside intent scope. Fail -> regenerate once -> else fallback
template. Hallucination incidents must be 0 (pilot gate G1).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.agent.templates import get_template

logger = logging.getLogger(__name__)


async def output_gate(state: AgentState) -> dict[str, Any]:
    """Node 6 — output scope check (TRD §4.2, gate 2).

    Post-generation: reject any uncited factual claim (fee/time/service/address).
    Fail -> regenerate once -> else fallback template.
    """
    intent_val = state.get("intent", "out_of_scope")
    response = state.get("response", "")
    lang = state.get("lang", "en")
    retry_count = state.get("retry_count", 0)

    # 1. Skip checks for static template intents
    if intent_val in ("out_of_scope", "medical_question", "abuse", "complaint"):
        return {"regenerate": False}

    # 2. Check if the response contains numbers, prices, timings, or location words
    # but lacks a citation tag "[source_ref:"
    factual_patterns = [
        r"\b\d+\b",                    # numbers (fees, slots)
        r"\b(rs\.?|inr|rupees)\b",     # currency indicators
        r"\b(am|pm|baje|time)\b",      # timings — word-bounded, else "am" matches inside "Namaste"
        r"\b(address|location|landmark|bhubaneswar)\b"  # location details
    ]
    
    response_lower = response.lower()
    has_factual_claims = any(re.search(pat, response_lower) for pat in factual_patterns)
    has_citation = "[source_ref:" in response_lower

    if has_factual_claims and not has_citation:
        logger.warning(f"Uncited factual claim detected in response. Has citation: {has_citation}")
        if retry_count < 1:
            logger.info("Attempting self-regeneration (Retry 1)")
            return {
                "regenerate": True,
                "retry_count": retry_count + 1
            }
        else:
            logger.warning(
                "Uncited claim persists after retry. Substituting with fallback template."
            )
            return {
                "regenerate": False,
                "response": get_template("out_of_scope", lang)
            }

    # All checks passed, proceed to output
    return {"regenerate": False}

