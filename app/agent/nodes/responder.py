"""Node 5 — responder (TRD §4.2).

Frontier model, KB/tool-grounded generation. Every factual claim (fee/time/
service/address) MUST carry a source_ref (citation requirement, Week 4 task 4.5).
Unreachable for out_of_scope / medical_question by graph topology — never invoked
for those intents.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.models.base import get_db
from app.agent.llm import query_llm

logger = logging.getLogger(__name__)


async def responder(state: dict[str, Any]) -> dict[str, Any]:
    """Node 5 — responder (TRD §4.2).

    Frontier model, KB/tool-grounded generation. Every factual claim (fee/time/
    service/address) MUST carry a source_ref.
    """
    tenant_id = state.get("tenant_id")
    conv_id = state.get("conversation_id")
    text = state.get("text", "")
    lang = state.get("lang", "en")
    tool_results = state.get("tool_results", [])
    
    # 1. Load context history (last 10 messages)
    db = get_db()
    history_str = ""
    try:
        cursor = db["messages"].find(
            {"conversation_id": conv_id, "tenant_id": tenant_id}
        ).sort("ts", -1).limit(10)
        messages = [doc async for doc in cursor]
        messages.reverse()
        
        history_lines = []
        for m in messages:
            role = "Patient" if m.get("direction") == "inbound" else "Clinic AI"
            content = m.get("text", "")
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines)
    except Exception as e:
        logger.warning(f"Failed to load message history for responder: {e}")

    # 2. Check for staff resolution summary
    resolution_summary = None
    try:
        res_msg = await db["messages"].find_one(
            {"conversation_id": conv_id, "tenant_id": tenant_id, "type": "resolution_summary"},
            sort=[("ts", -1)]
        )
        if res_msg:
            resolution_summary = res_msg.get("text")
    except Exception as e:
        logger.warning(f"Failed to load resolution summary: {e}")

    # 3. Format Grounded Facts from tool results
    grounded_facts = []
    for tr in tool_results:
        tool_name = tr.get("tool")
        if tool_name == "kb_search":
            for kb in tr.get("result", []):
                grounded_facts.append(
                    f"FAQ Question: {kb.get('question')}\n"
                    f"FAQ Answer: {kb.get('answer')}\n"
                    f"Source Reference: [source_ref: {kb.get('source_ref')}]"
                )
        elif tool_name == "slots_get":
            slots = tr.get("result", [])
            date_str = tr.get("date", "")
            doc_name = tr.get("practitioner_name", "Doctor")
            slots_str = ", ".join(s.get("start", "")[11:16] for s in slots[:8]) if slots else "No slots available"
            grounded_facts.append(
                f"Available Slots for {doc_name} on {date_str}: {slots_str}\n"
                f"Source Reference: [source_ref: slots_list]"
            )

    grounded_facts_str = "\n\n".join(grounded_facts) if grounded_facts else "No grounded facts found."

    # 4. Construct Prompt
    system_prompt = (
        "You are an empathetic, professional AI receptionist at Sharma Dental Clinic.\n"
        f"Answer the patient's query in their detected language ({lang}) using ONLY the provided Grounded Facts.\n\n"
        "Grounded Facts:\n"
        f"{grounded_facts_str}\n\n"
        "Strict Citation Rule:\n"
        "Any factual claim you make (such as fees, timings, address, services, doctor names) MUST be directly followed by its source reference from the Grounded Facts in brackets, e.g. [source_ref: hours_faq] or [source_ref: slots_list]. If no facts are provided, state that you don't know and will connect the patient to the clinic staff. Do not make up any facts.\n\n"
        "Tone and register:\n"
        "Always default to a respectful register (using 'आप' / 'ଆପଣ', never informal 'tum'/'tu'). Keep answers short and direct for chat interfaces."
    )

    if resolution_summary:
        system_prompt += (
            f"\n\nAdditional Context: Staff has just returned the conversation. "
            f"Resolution summary: {resolution_summary}. Acknowledge this resolution context gracefully if the patient follows up."
        )

    prompt = f"Conversation History:\n{history_str}\n\nPatient latest message: '{text}'"

    # Use settings configuration or default to gemini-2.5-flash
    model = settings.llm_model_responder or "google/gemini-2.5-flash"
    
    try:
        response_text = await query_llm(prompt, model, system_prompt=system_prompt, temperature=0.2)
        return {"response": response_text}
    except Exception as e:
        logger.error(f"Responder LLM call failed: {e}")
        return {"response": "I'm sorry, I'm having trouble processing that right now. I will notify the clinic staff to help you."}

