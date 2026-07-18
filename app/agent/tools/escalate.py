"""Tool — escalate to human (TRD §4.4).

Creates an escalations row and hands control to the handoff node. Every escalate
call is audited (choke point). Used by scope_gate for medical/complaint/abuse and
by low-confidence handoff triggers.
"""

from __future__ import annotations

from typing import Any


async def escalate(tenant_id: str, conversation_id: str, reason: str) -> dict[str, Any]:
    raise NotImplementedError("escalate — 06-engineering-plan task 5.1")
