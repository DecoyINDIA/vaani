from __future__ import annotations

import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def get_mock_response(prompt: str, model: str) -> str:
    """Provide rule-based responses to allow offline tests to pass without API keys."""
    # Split user prompt and system prompt
    parts = prompt.split(" ---SYSTEM_PROMPT--- ")
    user_prompt = parts[0]
    system_prompt = parts[1] if len(parts) > 1 else ""

    user_prompt_lower = user_prompt.lower()
    system_prompt_lower = system_prompt.lower()

    # Scope keyword matching to the actual user message when the calling prompt
    # wraps it — otherwise boilerplate like "Language detected: hi" pollutes
    # keyword checks (e.g. "hi" matching the greet branch).
    msg_match = re.search(
        r"(?:user message|patient latest message): '(.*)'", user_prompt_lower, re.DOTALL
    )
    if msg_match:
        user_prompt_lower = msg_match.group(1)

    is_classification = "intent" in system_prompt_lower or "classify" in system_prompt_lower

    if is_classification:
        # Prioritize safety and special gate intents first
        if any(w in user_prompt_lower for w in [
            "medical", "sar dard", "dard", "pain", "hurt", "treatment", "medic", "tablet",
            "dawai", "दर्द", "दवा", "ଯନ୍ତ୍ରଣା", "ଔଷଧ"
        ]):
            return '{"intent": "medical_question", "confidence": 0.98}'
        if any(w in user_prompt_lower for w in ["abuse", "stupid", "idiot", "nonsense"]):
            return '{"intent": "abuse", "confidence": 0.95}'
        if "complaint" in user_prompt_lower:
            return '{"intent": "complaint", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["human", "staff", "receptionist", "escalate"]):
            return '{"intent": "human_request", "confidence": 0.95}'

        # Appointment-mutation intents must be checked BEFORE "book": phrases like
        # "cancel my appointment" contain booking keywords too.
        if any(w in user_prompt_lower for w in ["reschedule", "change", "badal"]):
            return '{"intent": "reschedule", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["cancel", "radd"]):
            return '{"intent": "cancel", "confidence": 0.95}'
        if "status" in user_prompt_lower:
            return '{"intent": "booking_status", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["payment", "deposit", "razorpay"]):
            return '{"intent": "payment_query", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in [
            "appointment", "booking", "book", "milna", "ଦେଖା କରିବି", "अपॉइंटमेंट", "बुक"
        ]):
            return '{"intent": "book", "confidence": 0.95}'

        # FAQs
        if any(w in user_prompt_lower for w in ["timing", "timings", "hours", "open", "समय", "खुल", "ସମୟ"]):
            return '{"intent": "faq_hours", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["fee", "fees", "charge", "consultation", "शुल्क", "फीस", "ଫିସ୍"]):
            return '{"intent": "faq_fees", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["location", "address", "rasta", "kahan", "map", "पता", "ଠିକଣା"]):
            return '{"intent": "faq_location", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["doctor", "practitioner", "sharma"]):
            return '{"intent": "faq_doctor", "confidence": 0.90}'

        # Greetings (use split to avoid matching substrings like "hi" inside "hai")
        user_words = [w.strip("'\"!?.,") for w in user_prompt_lower.split()]
        if any(w in user_words for w in ["hello", "hi", "namaste", "hey"]):
            return '{"intent": "greet", "confidence": 1.0}'

        return '{"intent": "out_of_scope", "confidence": 1.0}'

    # --- Grounded responder mock ---
    # Route on the source_refs present inside the Grounded Facts block ONLY.
    # The citation-rule boilerplate always mentions "fees, timings, address" and
    # example refs, so keyword-matching the whole system prompt misroutes every
    # intent to the hours answer.
    facts_match = re.search(
        r"Grounded Facts:\n(.*?)(?:\n\nStrict Citation Rule|\Z)", system_prompt, re.DOTALL
    )
    facts = facts_match.group(1) if facts_match else ""
    facts_lower = facts.lower()

    if "source_ref: slots_list" in facts_lower:
        slot_match = re.search(r"Available Slots[^\n]*", facts)
        slots_line = slot_match.group(0) if slot_match else "Available slots found"
        return f"{slots_line}. Kripya bataiye kaun sa samay aapke liye theek rahega. [source_ref: slots_list]"

    faq_responses = {
        "faq_fees": "The consultation fee is Rs 500. [source_ref: faq_fees]",
        "faq_hours": "Sharma Dental Clinic is open from 9:00 AM to 6:00 PM Monday through Saturday. [source_ref: faq_hours]",
        "faq_location": "Sharma Dental Clinic is located near Main Market, Bhubaneswar, opposite HDFC Bank. [source_ref: faq_location]",
    }
    faq_keywords = {
        "faq_fees": ["fee", "fees", "charge", "consultation", "शुल्क", "फीस", "ଫିସ୍"],
        "faq_hours": ["timing", "hours", "open", "समय", "खुल", "ସମୟ"],
        "faq_location": ["location", "address", "rasta", "kahan", "map", "पता", "ଠିକଣା"],
    }
    # Prefer the FAQ fact that matches the user's question; kb_search can return
    # several entries, so refs alone are ambiguous.
    for ref, keywords in faq_keywords.items():
        if f"source_ref: {ref}" in facts_lower and any(w in user_prompt_lower for w in keywords):
            return faq_responses[ref]
    for ref, response in faq_responses.items():
        if f"source_ref: {ref}" in facts_lower:
            return response

    user_words = [w.strip("'\"!?.,") for w in user_prompt_lower.split()]
    if any(w in user_words for w in ["hello", "hi", "namaste", "hey"]):
        return "Namaste! Welcome to Sharma Dental Clinic. How can I help you today?"

    return "I'm sorry, I couldn't find information about that. I will escalate this to the clinic staff to help you. [source_ref: fallback]"


async def query_llm(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 500
) -> str:
    """Query OpenRouter API. Fallback to mock responses if key is missing or offline."""
    # Use fallback if key is not configured or in testing environment
    if not settings.openrouter_api_key:
        logger.debug(f"[LLM Mock] model={model} prompt={prompt[:100]}...")
        return get_mock_response(prompt + " ---SYSTEM_PROMPT--- " + (system_prompt or ""), model)
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DecoyINDIA/vaani",
        "X-Title": "Vaani Front Desk"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=data, timeout=30.0)
            if resp.status_code == 200:
                result = resp.json()
                return str(result["choices"][0]["message"]["content"]).strip()
            else:
                logger.error(f"OpenRouter API failed with status {resp.status_code}: {resp.text}")
                # Try fallback provider if configured
                if settings.llm_model_fallback_provider:
                    data["model"] = settings.llm_model_fallback_provider
                    resp_fallback = await client.post(url, headers=headers, json=data, timeout=30.0)
                    if resp_fallback.status_code == 200:
                        return str(resp_fallback.json()["choices"][0]["message"]["content"]).strip()
                raise RuntimeError(f"OpenRouter API error: {resp.text}")
    except Exception as e:
        logger.error(f"Error querying LLM: {e}")
        if settings.app_env == "dev" or not settings.openrouter_api_key:
            return get_mock_response(prompt + " ---SYSTEM_PROMPT--- " + (system_prompt or ""), model)
        raise
