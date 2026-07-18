"""Tool — escalate to human (TRD §4.4).

Creates an escalations row and hands control to the handoff node. Every escalate
call is audited (choke point). Used by scope_gate for medical/complaint/abuse and
by low-confidence handoff triggers.
"""

from __future__ import annotations

import logging
from datetime import datetime as dt, timezone
from typing import Any

from app.models.base import get_db

logger = logging.getLogger(__name__)


async def escalate(tenant_id: str, conversation_id: str, reason: str) -> dict[str, Any]:
    """Tool — escalate to human (TRD §4.4).

    Creates an escalations row and hands control to the handoff node.
    """
    db = get_db()
    now = dt.now(timezone.utc).replace(tzinfo=None)

    logger.info(f"Escalating conversation {conversation_id} due to: {reason}")

    # 1. Update conversation state to silenced ("human")
    await db["conversations"].update_one(
        {"_id": conversation_id, "tenant_id": tenant_id},
        {"$set": {"state": "human", "last_msg_at": now}}
    )

    # 2. Insert into escalations collection
    escalation = {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "reason": reason,
        "sla_notified_at": now,
        "ts": now
    }
    await db["escalations"].insert_one(escalation)

    # 3. Write to Audit Log (the choke point)
    await db["audit_log"].insert_one({
        "tenant_id": tenant_id,
        "actor": "agent",
        "event_type": "escalation",
        "conversation_id": conversation_id,
        "payload": {"reason": reason},
        "ts": now
    })

    return {"status": "success", "conversation_id": conversation_id, "reason": reason}

