"""Node 2 — intent classifier (TRD §4.1/§4.2 input gate).

Small model, temperature 0, few-shot per language. MUST emit a label from the
closed taxonomy with confidence >= threshold; below threshold twice -> handoff.
Closed set: greet, faq_hours, faq_location, faq_services, faq_fees, faq_doctor,
book, reschedule, cancel, booking_status, payment_query, reminder_response,
human_request, complaint, medical_question, smalltalk_min, out_of_scope, abuse.
"""

from __future__ import annotations

from typing import Any


async def intent(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("intent classify — 06-engineering-plan task 3.5")
