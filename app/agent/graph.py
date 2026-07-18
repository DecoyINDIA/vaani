"""LangGraph agent definition — the 7-node scoped state machine (TRD §1, §4).

Node order:
    lang_detect -> intent -> scope_gate -> tool_router -> responder
                -> output_gate -> handoff

Compliance-by-topology (06-engineering-plan §0, rule 3): the `responder` node is
UNREACHABLE for `out_of_scope` / `medical_question` intents by graph structure —
those route to static templates, never the LLM. Scope enforcement is a code path,
not a prompt (TRD §4.2, two mandatory gates).

Intent taxonomy is a closed set (TRD §4.1). The classifier must emit one of those
labels; below-threshold twice -> handoff.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State threaded through the graph. tenant_id is always present."""

    tenant_id: str
    conversation_id: str
    channel: str          # "wa" | "voice" — voice trims responses, no rich menus
    text: str
    lang: str             # hi | en | hi-Latn | or
    intent: str
    confidence: float
    tool_results: list[dict[str, Any]]
    response: str
    escalate: bool


def build_graph() -> Any:
    """Compile and return the LangGraph app. Wired in Week 3 (task 3.5)."""
    raise NotImplementedError("graph assembly — 06-engineering-plan task 3.5")
