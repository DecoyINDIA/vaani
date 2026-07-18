"""Tool — escalate to human (TRD §4.4).

Creates an escalations row and hands control to the handoff node. Every escalate
call is audited (choke point). Used by scope_gate for medical/complaint/abuse and
by low-confidence handoff triggers.
"""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime as dt
from typing import Any

from app import audit
from app.models.collections import Conversations, Escalations

logger = logging.getLogger(__name__)


async def escalate(tenant_id: str, conversation_id: str, reason: str) -> dict[str, Any]:
    """Tool — escalate to human (TRD §4.4).

    Creates an escalations row and hands control to the handoff node.
    """
    now = dt.now(UTC).replace(tzinfo=None)

    logger.info(f"Escalating conversation {conversation_id} due to: {reason}")

    # 1. Update conversation state to silenced ("human")
    await Conversations(tenant_id).update_one(
        {"_id": conversation_id},
        {"$set": {"state": "human", "last_msg_at": now}},
    )

    # 2. Insert into escalations collection
    await Escalations(tenant_id).insert_one(
        {
            "conversation_id": conversation_id,
            "reason": reason,
            "sla_notified_at": now,
            "ts": now,
        }
    )

    # 3. Record on the audit choke point
    await audit.record(
        tenant_id,
        actor="agent",
        event_type="escalation",
        payload={"reason": reason},
        conversation_id=conversation_id,
    )

    return {"status": "success", "conversation_id": conversation_id, "reason": reason}

