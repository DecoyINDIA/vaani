"""Shared agent state schema (TRD §4.1).

Split out from graph.py so node modules can type their `state` parameter as
`AgentState` without a circular import (graph.py imports the nodes).
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State threaded through the graph. tenant_id is always present."""

    tenant_id: str
    conversation_id: str
    channel: str          # "wa" | "voice" — voice trims responses, no rich menus
    text: str
    lang: str              # hi | en | hi-Latn | or
    intent: str
    confidence: float
    tool_results: list[dict[str, Any]]
    response: str
    escalate: bool
    retry_count: int
    regenerate: bool
