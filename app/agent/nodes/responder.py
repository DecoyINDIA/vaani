"""Node 5 — responder (TRD §4.2).

Frontier model, KB/tool-grounded generation. Every factual claim (fee/time/
service/address) MUST carry a source_ref (citation requirement, Week 4 task 4.5).
Unreachable for out_of_scope / restricted_advice by graph topology — never invoked
for those intents.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent.llm import query_llm
from app.agent.profile import load_profile
from app.agent.state import AgentState
from app.agent.templates import get_template
from app.agent.tenant_context import get_tenant_profile
from app.config import settings
from app.models.base import mongo_id_candidates
from app.models.collections import Contacts, Conversations, Messages, Practitioners

logger = logging.getLogger(__name__)


async def responder(state: AgentState) -> dict[str, Any]:
    """Node 5 — responder (TRD §4.2).

    Frontier model, KB/tool-grounded generation. Every factual claim (fee/time/
    service/address) MUST carry a source_ref.
    """
    tenant_id: str = state.get("tenant_id") or ""
    conv_id = state.get("conversation_id")
    text = state.get("text", "")
    lang = state.get("lang", "en")
    tool_results = state.get("tool_results", [])
    business = await load_profile(tenant_id)
    customer = business.customer_term
    
    # 1. Load context history (last 10 messages)
    messages_acc = Messages(tenant_id)
    history_str = ""
    try:
        cursor = messages_acc.find(
            {"conversation_id": conv_id}
        ).sort("ts", -1).limit(10)
        messages = [doc async for doc in cursor]
        messages.reverse()
        
        history_lines = []
        for m in messages:
            role = "Customer" if m.get("direction") == "inbound" else "Assistant"
            content = m.get("text", "")
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines)
    except Exception as e:
        logger.warning(f"Failed to load message history for responder: {e}")

    # 2. Check for staff resolution summary
    resolution_summary = None
    try:
        res_msg = await messages_acc.find_one(
            {"conversation_id": conv_id, "type": "resolution_summary"},
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
            staff_name = tr.get("practitioner_name") or "our team"
            slots_str = ", ".join(s.get("start", "")[11:16] for s in slots[:8]) if slots else "No slots available"
            grounded_facts.append(
                f"Available Slots for {staff_name} on {date_str}: {slots_str}\n"
                f"Source Reference: [source_ref: slots_list]"
            )

    grounded_facts_str = "\n\n".join(grounded_facts) if grounded_facts else "No grounded facts found."

    # Load contact profile for returning-customer memory lookup
    contact = None
    try:
        conv = await Conversations(tenant_id).find_one(
            {"_id": {"$in": mongo_id_candidates(str(conv_id))}}
        )
        if conv and conv.get("contact_id"):
            contact = await Contacts(tenant_id).find_one({"_id": conv["contact_id"]})
    except Exception as e:
        logger.warning(f"Failed to load contact profile for responder: {e}")

    tenant_profile = await get_tenant_profile(tenant_id)
    name = tenant_profile["name"]

    # 4. Construct Prompt
    system_prompt = (
        f"You are an empathetic, professional AI receptionist at {name}.\n"
        f"Answer the {customer}'s query in their detected language ({lang}) using ONLY the provided Grounded Facts.\n\n"
        "Grounded Facts:\n"
        f"{grounded_facts_str}\n\n"
        "Strict Citation Rule:\n"
        f"Any factual claim you make (such as fees, timings, address, services, staff names) MUST be directly followed by its source reference from the Grounded Facts in brackets, e.g. [source_ref: hours_faq] or [source_ref: slots_list]. If no facts are provided, state that you don't know and will connect the {customer} to our team. Do not make up any facts.\n\n"
        "Tone and register:\n"
        "Always default to a respectful register (using 'आप' / 'ଆପଣ', never informal 'tum'/'tu'). Keep answers short and direct for chat interfaces."
    )

    if contact:
        customer_name = contact.get("name")
        profile = contact.get("profile", {})
        pref_prac_id = profile.get("preferred_practitioner_id") or profile.get("preferred_practitioner")
        last_service = profile.get("last_service")
        
        pref_prac_name = None
        if pref_prac_id:
            try:
                prac = await Practitioners(tenant_id).find_one({"_id": pref_prac_id})
                if prac:
                    pref_prac_name = prac.get("name")
            except Exception:
                pass
                
        # Check intent to offer one-tap rebook
        if state.get("intent") == "book" and last_service and pref_prac_name:
            greeting_name = f" {customer_name} Ji" if customer_name else ""
            system_prompt += (
                f"\n\nReturning Customer Event: This is a returning {customer}{greeting_name}. "
                f"Their preferred {business.staff_term} is {pref_prac_name} and last service was {last_service}. "
                f"Offer the {customer} a one-tap rebook: ask if they want to book the same {last_service} with {pref_prac_name}."
            )
        elif customer_name:
            system_prompt += f"\n\nPersonalization: Greet the {customer} by their name '{customer_name} Ji' politely."

    if resolution_summary:
        system_prompt += (
            f"\n\nAdditional Context: Staff has just returned the conversation. "
            f"Resolution summary: {resolution_summary}. Acknowledge this resolution context gracefully if the {customer} follows up."
        )

    prompt = f"Conversation History:\n{history_str}\n\nCustomer latest message: '{text}'"

    # Use settings configuration or default to gemini-2.5-flash
    model = settings.llm_model_responder or "google/gemini-2.5-flash"
    
    try:
        response_text = await query_llm(prompt, model, system_prompt=system_prompt, temperature=0.2)
        return {"response": response_text}
    except Exception as e:
        logger.error("Responder LLM call failed: %s", type(e).__name__)
        return {
            "agent_error": "llm_unavailable",
            "escalate": True,
            "response": get_template("handoff_ack", lang),
        }

