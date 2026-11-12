"""LangGraph agent definition — the 7-node scoped state machine (TRD §1, §4).

Node order:
    lang_detect -> intent -> scope_gate -> tool_router -> responder
                -> output_gate -> handoff

Compliance-by-topology (06-engineering-plan §0, rule 3): the `responder` node is
UNREACHABLE for `out_of_scope` / `restricted_advice` intents by graph structure —
those route to static templates, never the LLM. Scope enforcement is a code path,
not a prompt (TRD §4.2, two mandatory gates).

Intent taxonomy is a closed set (TRD §4.1). The classifier must emit one of those
labels; below-threshold twice -> handoff.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.nodes.handoff import handoff
from app.agent.nodes.intent import intent
from app.agent.nodes.lang_detect import lang_detect
from app.agent.nodes.output_gate import output_gate
from app.agent.nodes.responder import responder
from app.agent.nodes.scope_gate import scope_gate
from app.agent.nodes.tool_router import tool_router
from app.agent.state import AgentState

__all__ = ["AgentState", "build_graph"]


def build_graph() -> Any:
    """Compile and return the LangGraph app. Wired in Week 3 (task 3.5)."""
    workflow = StateGraph(AgentState)
    
    # 1. Add all nodes
    workflow.add_node("lang_detect", lang_detect)
    workflow.add_node("intent", intent)
    workflow.add_node("scope_gate", scope_gate)
    workflow.add_node("tool_router", tool_router)
    workflow.add_node("responder", responder)
    workflow.add_node("output_gate", output_gate)
    workflow.add_node("handoff", handoff)
    
    # 2. Set entry point
    workflow.set_entry_point("lang_detect")
    
    # 3. Static edges
    workflow.add_edge("lang_detect", "intent")
    workflow.add_edge("intent", "scope_gate")
    
    # 4. Conditional edge from scope_gate
    def route_scope_gate(state: AgentState) -> str:
        if state.get("escalate"):
            return "handoff"
        # If response is already set by a static template, go straight to output_gate
        if state.get("response"):
            return "output_gate"
        return "tool_router"
        
    workflow.add_conditional_edges(
        "scope_gate",
        route_scope_gate,
        {
            "handoff": "handoff",
            "output_gate": "output_gate",
            "tool_router": "tool_router"
        }
    )
    
    # 5. Core flow edges
    def route_tool_router(state: AgentState) -> str:
        if state.get("escalate"):
            return "handoff"
        if (
            state.get("channel") == "wa"
            and state.get("intent") in {"book", "reschedule", "cancel", "booking_status"}
        ):
            return END
        return "responder"

    workflow.add_conditional_edges(
        "tool_router",
        route_tool_router,
        {"handoff": "handoff", "responder": "responder", END: END},
    )
    workflow.add_conditional_edges(
        "responder",
        lambda state: "handoff" if state.get("escalate") else "output_gate",
        {"handoff": "handoff", "output_gate": "output_gate"},
    )
    
    # 6. Conditional edge from output_gate for regeneration
    def route_output_gate(state: AgentState) -> str:
        if state.get("regenerate"):
            return "responder"
        return END
        
    workflow.add_conditional_edges(
        "output_gate",
        route_output_gate,
        {
            "responder": "responder",
            END: END
        }
    )
    
    # 7. Edge from handoff
    workflow.add_edge("handoff", END)
    
    return workflow.compile()

