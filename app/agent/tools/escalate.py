"""Tool — escalate to human (TRD §4.4).

Creates an escalations row and hands control to the handoff node. Every escalate
call is audited (choke point). Used by scope_gate for restricted advice/complaint/abuse and
by low-confidence handoff triggers.
"""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime as dt
from typing import Any

from app import audit
from app.agent.templates import get_template
from app.channels.whatsapp import AmbiguousDeliveryError, send_template
from app.models.base import mongo_id_candidates
from app.models.collections import Contacts, Conversations, Escalations, Tenants, Users
from app.workers.escalations import escalation_sla, escalation_variables

logger = logging.getLogger(__name__)


async def escalate(
    tenant_id: str,
    conversation_id: str,
    reason: str,
    *,
    lang: str = "en",
    now: dt | None = None,
) -> dict[str, Any]:
    """Tool — escalate to human (TRD §4.4).

    Creates an escalations row and hands control to the handoff node.
    """
    aware_now = now or dt.now(UTC)
    if aware_now.tzinfo is None:
        aware_now = aware_now.replace(tzinfo=UTC)
    now_naive = aware_now.astimezone(UTC).replace(tzinfo=None)

    logger.info(f"Escalating conversation {conversation_id} due to: {reason}")

    conversation_query = {"_id": {"$in": mongo_id_candidates(conversation_id)}}
    await Conversations(tenant_id).update_one(
        conversation_query,
        {"$set": {"state": "human", "last_msg_at": now_naive}},
    )
    conversation = await Conversations(tenant_id).find_one(conversation_query)
    tenant = await Tenants.find_by_id(tenant_id) or {}
    sla_mode, sla_due_at = escalation_sla(tenant, aware_now)

    escalations = Escalations(tenant_id)
    existing = await escalations.find_one(
        {"conversation_id": conversation_id, "status": "open"}
    )
    if existing:
        return {"status": "duplicate", "conversation_id": conversation_id, "reason": reason}

    inserted = await escalations.insert_one(
        {
            "conversation_id": conversation_id,
            "reason": reason,
            "status": "open",
            "notification_status": "pending",
            "sla_mode": sla_mode,
            "sla_due_at": sla_due_at.replace(tzinfo=None) if sla_due_at else None,
            "owner_notification_status": "not_due",
            "ts": now_naive,
        }
    )

    recipient = await Users(tenant_id).find_one(
        {"role": {"$in": ["staff", "owner"]}, "status": {"$ne": "inactive"}}
    )
    wa_id = (recipient or {}).get("wa_id") or (recipient or {}).get("phone")
    notification_status = "missing_recipient"
    notification_error = None
    if wa_id:
        contact = None
        if conversation and conversation.get("contact_id") is not None:
            contact = await Contacts(tenant_id).find_one(
                {
                    "_id": {
                        "$in": mongo_id_candidates(str(conversation["contact_id"]))
                    }
                }
            )
        try:
            await send_template(
                tenant_id,
                str(wa_id),
                "escalation_alert_staff",
                escalation_variables(tenant, conversation_id, reason, contact),
                operation_key=f"escalation:{conversation_id}",
            )
            notification_status = "sent"
        except AmbiguousDeliveryError as e:
            notification_status = "unknown"
            notification_error = str(e)
        except Exception as e:
            notification_status = "failed"
            notification_error = str(e)
    notification: dict[str, Any] = {
        "notification_status": notification_status,
        "notification_updated_at": dt.now(UTC).replace(tzinfo=None),
    }
    if notification_error:
        notification["notification_error"] = notification_error
    if notification_status == "sent":
        notification["sla_notified_at"] = dt.now(UTC).replace(tzinfo=None)
    await escalations.update_one({"_id": inserted.inserted_id}, {"$set": notification})

    await audit.record(
        tenant_id,
        actor="agent",
        event_type="escalation",
        payload={"reason": reason},
        conversation_id=conversation_id,
    )

    result = {"status": "success", "conversation_id": conversation_id, "reason": reason}
    if sla_mode == "out_of_hours":
        result["patient_message"] = get_template("handoff_after_hours", lang)
    return result

