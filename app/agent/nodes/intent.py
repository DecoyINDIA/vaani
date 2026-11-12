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
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.agent.llm import query_llm
from app.agent.profile import BusinessProfile, load_profile
from app.agent.state import AgentState
from app.booking.timefmt import DEFAULT_TIMEZONE, tenant_timezone
from app.config import settings
from app.models.collections import Messages, Tenants

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


def build_system_prompt(
    profile: BusinessProfile,
    *,
    today_iso: str = "",
    weekday: str = "",
) -> str:
    """Classifier instructions worded for this tenant's kind of business."""
    restricted = "; ".join(profile.restricted_topics)
    examples = "".join(
        f"{i}. Text: '{example}' -> "
        '{"intent": "restricted_advice", "confidence": 0.98}\n'
        for i, example in enumerate(profile.restricted_examples, start=7)
    )
    today_context = f"Today is {weekday}, {today_iso}.\n" if today_iso and weekday else ""

    return (
        f"You are an expert intent classifier for the AI front-desk agent of {profile.name}, "
        f"a {profile.business_type}.\n"
        f"{today_context}"
        "Analyze the user's message and output a JSON object with the following schema:\n"
        "- \"intent\": exactly one of the closed taxonomy labels\n"
        "- \"confidence\": float between 0.0 and 1.0\n"
        "- \"date\": requested date in YYYY-MM-DD format (or null). "
        "Rules: resolve relative dates against today; ambiguous 'kal' means tomorrow; "
        "never output a past date; null if user gave none.\n"
        "- \"time\": requested time in 24-hour HH:MM format (or null)\n"
        f"- \"practitioner_hint\": requested {profile.staff_term} name (string or null)\n"
        "- \"service_hint\": requested service or reason (string or null)\n\n"
        f"The \"intent\" key MUST be exactly one of the following labels:\n{', '.join(sorted(TAXONOMY))}\n\n"
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


def build_intent_prompts(
    text: str,
    lang: str,
    business_type: str = "clinic",
    *,
    profile: BusinessProfile | None = None,
    today_iso: str = "",
    weekday: str = "",
    history: str = "",
) -> tuple[str, str]:
    """Pure prompt builder for structured understanding."""
    if profile is None:
        profile = BusinessProfile(name="our business", business_type=business_type)
    system_prompt = build_system_prompt(profile, today_iso=today_iso, weekday=weekday)
    hist_text = history.strip() if history and history.strip() else "(none)"
    user_prompt = (
        f"Language detected: {lang}\n"
        f"Recent conversation (oldest first):\n"
        f"{hist_text}\n"
        f"User message: '{text}'"
    )
    return system_prompt, user_prompt


def parse_understanding(raw: str, *, today: date) -> dict[str, Any]:
    """Parse raw LLM response into intent and optional structured fields.

    Strips code fences, parses JSON, and validates against TAXONOMY.
    Validates date within [today, today + 90 days], time as HH:MM, and trims hints.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise ValueError(f"Unparseable intent response: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Intent response is not a JSON object")

    detected_intent = str(data.get("intent", "")).strip()
    detected_intent = LEGACY_INTENT_ALIASES.get(detected_intent, detected_intent)
    try:
        confidence = float(data.get("confidence", 0.0))
    except (ValueError, TypeError):
        confidence = 0.0

    if detected_intent not in TAXONOMY:
        return {"intent": "out_of_scope", "confidence": 0.0}

    result: dict[str, Any] = {
        "intent": detected_intent,
        "confidence": confidence,
    }

    raw_date = data.get("date")
    if isinstance(raw_date, str) and raw_date.strip():
        try:
            parsed_d = date.fromisoformat(raw_date.strip())
            if today <= parsed_d <= today + timedelta(days=90):
                result["req_date"] = parsed_d.isoformat()
        except ValueError:
            pass

    raw_time = data.get("time")
    if isinstance(raw_time, str) and raw_time.strip():
        time_str = raw_time.strip()
        if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_str):
            result["req_time"] = time_str

    raw_practitioner = data.get("practitioner_hint")
    if isinstance(raw_practitioner, str) and raw_practitioner.strip():
        result["practitioner_hint"] = raw_practitioner.strip()[:60]

    raw_service = data.get("service_hint")
    if isinstance(raw_service, str) and raw_service.strip():
        result["service_hint"] = raw_service.strip()[:60]

    return result


def parse_intent_response(raw: str) -> tuple[str, float]:
    """Parse raw LLM response into (intent, confidence)."""
    parsed = parse_understanding(raw, today=date.today())
    return parsed["intent"], parsed["confidence"]


async def intent(state: AgentState) -> dict[str, Any]:
    """Node 2 — intent classifier & structured understand (TRD §4.1/§4.2 input gate).

    Small model, temperature 0, JSON mode. Emits closed-set intent + optional date/time/hints.
    """
    text = state.get("text", "").strip()
    lang = state.get("lang", "en")
    tenant_id = state.get("tenant_id") or ""
    conversation_id = state.get("conversation_id") or ""

    if not text:
        return {"intent": "out_of_scope", "confidence": 0.0}

    # Timezone & current date for tenant
    try:
        tenant = await Tenants.find_by_id(tenant_id) if tenant_id else None
        tz = tenant_timezone(tenant)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    today = datetime.now(tz).date()
    today_iso = today.isoformat()
    weekday = today.strftime("%A")

    # Fetch last 6 messages from Messages(tenant_id)
    history = ""
    try:
        if conversation_id and tenant_id:
            cursor = (
                Messages(tenant_id)
                .find({"conversation_id": conversation_id})
                .sort("ts", -1)
                .limit(6)
            )
            docs = await cursor.to_list(length=6)
            docs.reverse()
            lines: list[str] = []
            for m in docs:
                direction = m.get("direction")
                sender = "Patient" if direction == "inbound" else "Clinic"
                body = m.get("text") or ""
                if not body and m.get("type") == "interactive":
                    body = "(interactive option)"
                sanitized = body[:200].replace("'", "’")
                lines.append(f"{sender}: {sanitized}")
            history = "\n".join(lines)
    except Exception as hist_err:
        logger.warning("Could not fetch conversation history: %s", hist_err)
        history = ""

    # Setup model
    model = settings.llm_model_classifier or "google/gemini-2.5-flash-lite"

    profile = await load_profile(tenant_id)
    system_prompt, prompt = build_intent_prompts(
        text,
        lang,
        profile.business_type,
        profile=profile,
        today_iso=today_iso,
        weekday=weekday,
        history=history,
    )

    try:
        response_text = await query_llm(
            prompt,
            model,
            system_prompt=system_prompt,
            temperature=0.0,
            json_mode=True,
            node="intent",
            tenant_id=tenant_id,
        )
        return parse_understanding(response_text, today=today)
    except Exception as e:
        logger.error("Intent classification failed: %s", type(e).__name__)
        return {
            "intent": "out_of_scope",
            "confidence": 0.0,
            "agent_error": "llm_unavailable",
        }


