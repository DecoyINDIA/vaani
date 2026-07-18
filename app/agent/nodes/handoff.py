"""Node 7 — handoff manager (TRD §4.4).

Triggers: human_request, 2x low-confidence, medical/complaint, abuse. Sets
conversations.state = human, silences the bot for that thread, fires a WhatsApp
template alert to on-duty staff (<=30s), starts SLA timers. "Resolve & return"
flips state back to bot with a context summary injected. All transitions audited.
"""

from __future__ import annotations

from typing import Any


async def handoff(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("handoff — 06-engineering-plan task 5.1")
