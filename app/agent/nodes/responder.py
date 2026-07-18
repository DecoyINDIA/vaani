"""Node 5 — responder (TRD §4.2).

Frontier model, KB/tool-grounded generation. Every factual claim (fee/time/
service/address) MUST carry a source_ref (citation requirement, Week 4 task 4.5).
Unreachable for out_of_scope / medical_question by graph topology — never invoked
for those intents.
"""

from __future__ import annotations

from typing import Any


async def responder(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("responder — 06-engineering-plan task 4.5")
