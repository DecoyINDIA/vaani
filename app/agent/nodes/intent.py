"""Node 2 — intent classifier (TRD §4.1/§4.2 input gate).

Small model, temperature 0, few-shot per language. MUST emit a label from the
closed taxonomy with confidence >= threshold; below threshold twice -> handoff.
Closed set: greet, faq_hours, faq_location, faq_services, faq_fees, faq_doctor,
book, reschedule, cancel, booking_status, payment_query, reminder_response,
human_request, complaint, medical_question, smalltalk_min, out_of_scope, abuse.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.agent.llm import query_llm

logger = logging.getLogger(__name__)

TAXONOMY = {
    "greet", "faq_hours", "faq_location", "faq_services", "faq_fees", "faq_doctor",
    "book", "reschedule", "cancel", "booking_status", "payment_query", "reminder_response",
    "human_request", "complaint", "medical_question", "smalltalk_min", "out_of_scope", "abuse"
}


async def intent(state: dict[str, Any]) -> dict[str, Any]:
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

    system_prompt = (
        "You are an expert intent classifier for a dental clinic AI front-desk agent. "
        "Analyze the user's message and output a JSON object containing the keys \"intent\" and \"confidence\".\n"
        f"The \"intent\" key MUST be exactly one of the following labels:\n{', '.join(sorted(TAXONOMY))}\n\n"
        "The \"confidence\" key must be a float between 0.0 and 1.0 representing your certainty.\n\n"
        "Intent Guidance:\n"
        "- greet: Greeting or saying hello (e.g. 'hi', 'namaste', 'hello')\n"
        "- faq_hours: Clinic timings/hours (e.g. 'timings kya hai', 'when does it open')\n"
        "- faq_location: Clinic address, location, map link, directions\n"
        "- faq_services: Available services, treatments (e.g. 'root canal', 'cleaning')\n"
        "- faq_fees: Consultation fee, price, costs\n"
        "- faq_doctor: Doctor details, who is the doctor (e.g. 'Dr. Sharma')\n"
        "- book: Booking a new appointment (e.g. 'appointment book karna hai')\n"
        "- reschedule: Changing/moving an appointment\n"
        "- cancel: Cancelling an appointment\n"
        "- booking_status: Checking existing booking status\n"
        "- payment_query: Queries about payment links, deposit, Razorpay\n"
        "- reminder_response: User responding to a reminder (e.g. 'yes I will come')\n"
        "- human_request: Explicit request for staff/human/receptionist\n"
        "- complaint: Dissatisfaction or complaint about service\n"
        "- medical_question: Medical questions/advice (e.g. 'my tooth hurts what medicine to take')\n"
        "- smalltalk_min: Canned pleasantry (e.g. 'how are you', 'thank you')\n"
        "- abuse: Bad language, threats, abuse\n"
        "- out_of_scope: General questions not related to the dental clinic\n\n"
        "Few-shot Examples:\n"
        "1. Text: 'hi' -> {\"intent\": \"greet\", \"confidence\": 1.0}\n"
        "2. Text: 'appointment mil sakta hai?' -> {\"intent\": \"book\", \"confidence\": 0.95}\n"
        "3. Text: 'consultation charge kitna hai?' -> {\"intent\": \"faq_fees\", \"confidence\": 0.95}\n"
        "4. Text: 'mujhe dr sharma se milna hai' -> {\"intent\": \"book\", \"confidence\": 0.90}\n"
        "5. Text: 'mere daant me dard hai kaunsi dawai lu?' -> {\"intent\": \"medical_question\", \"confidence\": 0.98}\n"
        "6. Text: 'weather in bhubaneswar' -> {\"intent\": \"out_of_scope\", \"confidence\": 1.0}\n"
        "7. Text: 'staff se baat karayein' -> {\"intent\": \"human_request\", \"confidence\": 0.95}\n"
    )

    prompt = f"Language detected: {lang}\nUser message: '{text}'"

    try:
        response_text = await query_llm(prompt, model, system_prompt=system_prompt, temperature=0.0)
        
        # Clean up JSON delimiters if LLM wrapped in markdown codeblock
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        detected_intent = data.get("intent", "").strip()
        confidence = float(data.get("confidence", 0.0))

        if detected_intent not in TAXONOMY:
            detected_intent = "out_of_scope"
            confidence = 0.0

        return {"intent": detected_intent, "confidence": confidence}
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Default fallback
        return {"intent": "out_of_scope", "confidence": 0.0}

