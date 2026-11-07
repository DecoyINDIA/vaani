"""Node 6 — output scope check (TRD §4.2, gate 2).

Post-generation: reject any uncited factual claim (fee/time/service/address) and
any content outside intent scope. Fail -> regenerate once -> else fallback
template. Hallucination incidents must be 0 (pilot gate G1).
"""

from __future__ import annotations

import json
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

    allowed_sources: dict[str, str] = {}
    for tool_result in state.get("tool_results", []):
        if tool_result.get("tool") == "kb_search":
            for fact in tool_result.get("result", []):
                source_ref = fact.get("source_ref")
                if source_ref:
                    allowed_sources[str(source_ref).lower()] = json.dumps(fact, default=str).lower()
        elif tool_result.get("tool") == "slots_get":
            allowed_sources["slots_list"] = json.dumps(tool_result, default=str).lower()

    cited_refs = {ref.strip() for ref in re.findall(r"\[source_ref:\s*([^\]]+)\]", response_lower)}
    invalid_citation = bool(cited_refs - allowed_sources.keys())
    cited_source_text = " ".join(
        allowed_sources[ref] for ref in cited_refs if ref in allowed_sources
    )
    unsupported_numbers = bool(
        cited_refs
        and any(
            number not in cited_source_text
            for number in re.findall(r"\d+(?:[.,]\d+)?", response)
        )
    )

    if (has_factual_claims and not has_citation) or invalid_citation or unsupported_numbers:
        logger.warning(
            "Grounding violation: citation=%s invalid_ref=%s unsupported_number=%s",
            has_citation,
            invalid_citation,
            unsupported_numbers,
        )
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

