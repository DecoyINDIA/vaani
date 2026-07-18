"""Node 6 — output scope check (TRD §4.2, gate 2).

Post-generation: reject any uncited factual claim (fee/time/service/address) and
any content outside intent scope. Fail -> regenerate once -> else fallback
template. Hallucination incidents must be 0 (pilot gate G1).
"""

from __future__ import annotations

from typing import Any


async def output_gate(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("output gate — 06-engineering-plan task 4.5")
