"""Node 3 — input scope gate (TRD §4.2, gate 1).

Routes by intent. medical_question / out_of_scope / abuse / complaint never reach
the LLM responder — they go to static templates + escalate flags. This is the
first of the two mandatory gates that make Meta-policy compliance a code path.
"""

from __future__ import annotations

from typing import Any


async def scope_gate(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("scope gate — 06-engineering-plan task 3.5")
