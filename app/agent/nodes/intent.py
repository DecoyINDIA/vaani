"""Node 2 — intent classifier (TRD §4.1/§4.2 input gate).

Small model, temperature 0, few-shot per language. MUST emit a label from the
closed taxonomy with confidence >= threshold; below threshold twice -> handoff.
Closed set: greet, faq_hours, faq_location, faq_services, faq_fees, faq_staff,
book, reschedule, cancel, booking_status, payment_query, reminder_response,
human_request, complaint, restricted_advice, smalltalk_min, out_of_scope, abuse.

The labels are industry-neutral. What counts as ``restricted_advice`` and how
the business is described come from the tenant's business profile.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.llm import query_llm
from app.agent.profile import BusinessProfile, load_profile
from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

TAXONOMY = {
    "greet", "faq_hours", "faq_location", "faq_services", "faq_fees", "faq_staff",
    "book", "reschedule", "cancel", "booking_status", "payment_query", "reminder_response",
    "human_request", "complaint", "restricted_advice", "smalltalk_min", "out_of_scope", "abuse"
}

# Labels used before the taxonomy became industry-neutral. A model that still
# emits one is mapped rather than dropped to out_of_scope, so the safety gate holds.
LEGACY_INTENT_ALIASES = {
    "medical_question": "restricted_advice",
    "faq_doctor": "faq_staff",
}


def build_system_prompt(profile: BusinessProfile) -> str:
    """Classifier instructions worded for this tenant's kind of business."""
    restricted = "; ".join(profile.restricted_topics)
    examples = "".join(
        f"{i}. Text: '{example}' -> "
        '{"intent": "restricted_advice", "confidence": 0.98}\n'
        for i, example in enumerate(profile.restricted_examples, start=7)
    )
    return (
        f"You are an expert intent classifier for the AI front-desk agent of {profile.name}, "
        f"a {profile.business_type}. "
        "Analyze the user's message and output a JSON object containing the keys \"intent\" and \"confidence\".\n"
        f"The \"intent\" key MUST be exactly one of the following labels:\n{', '.join(sorted(TAXONOMY))}\n\n"
        "The \"confidence\" key must be a float between 0.0 and 1.0 representing your certainty.\n\n"
        "Intent Guidance:\n"
        "- greet: Greeting or saying hello (e.g. 'hi', 'namaste', 'hello')\n"
        "- faq_hours: Opening hours/timings (e.g. 'timings kya hai', 'when does it open')\n"
        "- faq_location: Address, location, map link, directions\n"
        "- faq_services: What services or products are offered\n"
        "- faq_fees: Prices, fees, charges, costs\n"
        f"- faq_staff: Questions about the {profile.staff_term} or team (who they are, their experience)\n"
        "- book: Booking a new appointment (e.g. 'appointment book karna hai')\n"
        "- reschedule: Changing/moving an appointment\n"
        "- cancel: Cancelling an appointment\n"
        "- booking_status: Checking existing booking status\n"
        "- payment_query: Queries about payment links, deposit, Razorpay\n"
        "- reminder_response: User responding to a reminder (e.g. 'yes I will come')\n"
        "- human_request: Explicit request for staff/human/receptionist\n"
        "- complaint: Dissatisfaction or complaint about service\n"
        "- restricted_advice: Requests for advice this business must not give over chat "
        f"({restricted})\n"
        "- smalltalk_min: Canned pleasantry (e.g. 'how are you', 'thank you')\n"
        "- abuse: Bad language, threats, abuse\n"
        "- out_of_scope: General questions not related to this business\n\n"
        "Few-shot Examples:\n"
        "1. Text: 'hi' -> {\"intent\": \"greet\", \"confidence\": 1.0}\n"
        "2. Text: 'appointment mil sakta hai?' -> {\"intent\": \"book\", \"confidence\": 0.95}\n"
        "3. Text: 'charge kitna hai?' -> {\"intent\": \"faq_fees\", \"confidence\": 0.95}\n"
        "4. Text: 'mujhe kal milna hai, time milega?' -> {\"intent\": \"book\", \"confidence\": 0.90}\n"
        "5. Text: 'weather today' -> {\"intent\": \"out_of_scope\", \"confidence\": 1.0}\n"
        "6. Text: 'staff se baat karayein' -> {\"intent\": \"human_request\", \"confidence\": 0.95}\n"
        f"{examples}"
    )


async def intent(state: AgentState) -> dict[str, Any]:
    """Node 2 — intent classifier (TRD §4.1/§4.2 input gate).

    Small model, temperature 0, few-shot per language. MUST emit a label from the
    closed taxonomy with confidence >= threshold; below threshold twice -> handoff.
    """
    text = state.get("text", "").strip()
    lang = state.get("lang", "en")

    if not text:
        return {"intent": "out_of_scope", "confidence": 0.0}

    # Setup model (use settings configuration or default to gemini-2.5-flash-lite)
    model = settings.llm_model_classifier or "google/gemini-2.5-flash-lite"

    system_prompt = build_system_prompt(await load_profile(state.get("tenant_id") or ""))

    prompt = f"Language detected: {lang}\nUser message: '{text}'"

    try:
        response_text = await query_llm(
            prompt,
            model,
            system_prompt=system_prompt,
            temperature=0.0,
            json_mode=True,
            node="intent",
            tenant_id=state.get("tenant_id") or "",
        )
        
        # Clean up JSON delimiters if LLM wrapped in markdown codeblock
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        detected_intent = data.get("intent", "").strip()
        detected_intent = LEGACY_INTENT_ALIASES.get(detected_intent, detected_intent)
        confidence = float(data.get("confidence", 0.0))

        if detected_intent not in TAXONOMY:
            detected_intent = "out_of_scope"
            confidence = 0.0

        return {"intent": detected_intent, "confidence": confidence}
    except Exception as e:
        logger.error("Intent classification failed: %s", type(e).__name__)
        return {
            "intent": "out_of_scope",
            "confidence": 0.0,
            "agent_error": "llm_unavailable",
        }

